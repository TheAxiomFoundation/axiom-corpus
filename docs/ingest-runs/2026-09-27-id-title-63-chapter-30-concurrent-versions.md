# Idaho Title 63 chapter 30: the 2027 text of §§63-3022E and 63-3025D as variant rows (2026-09-27)

Follow-up 4 of the recovery sibling-scope audit (#757,
`docs/ingest-runs/2026-09-27-recovery-sibling-scopes-audit.md`, "Idaho"). The
official pages for Idaho Code §§63-3022E and 63-3025D print two versions of
each section, "[effective until January 1, 2027]" and "[effective January 1,
2027]". Both Idaho chapter 30 carriers hold only the first:

- `us-id/statute/2026-07-31-id-title-63-chapter-30-successor` (seven rows from
  the pages retrieved 2026-07-13);
- `us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30` (the
  whole chapter, from the pages retrieved 2026-09-14).

| scope | rows | coverage |
|---|---:|---|
| `us-id/statute/2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30` | 166 | complete, 166 / 166, 0 missing, 0 extra |

The scope is the 2026-09-14 chapter scope plus two variant rows:

- `us-id/statute/63-3022E--effective-2027-01-01`
- `us-id/statute/63-3025D--effective-2027-01-01`

It is re-extracted offline from the 165 pages the 2026-09-14 scope retained.
Its bytes live outside git (`docs/corpus-storage.md`). The signing commit
follows this note's last edit and does three things:

- adds the scope's signed ingest manifest;
- adds its lock file,
  `.axiom/corpus-locks/us-id/statute/2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30.json`;
- uploads any of its content-addressed objects R2 lacks to `objects/sha256/`,
  which publishes nothing (AGENTS.md).

This work adds and edits no release selector, and it publishes, loads and
activates nothing.

The work started on 2026-09-27 on `origin/main` f1916d73b. It was rebuilt on
2026-10-12 on `origin/main` eabe4ed94, after the switch that moved corpus bytes
into lock files (b33d5bf08). The provisions, inventory and coverage are
byte-identical to the pre-rebuild extraction at 35c41816b.

Evidence for this note is kept outside the repository in
`~/reviews/axiom-corpus-id-concurrent-versions/`:
- the top level and `round2/`: the review reports;
- `evidence/`: the recorded checks, the live check, the mutation results, the
  Subfleet job metadata and the GitNexus output.

## The whole chapter

All 162 section pages the chapter scope retained were read three ways. A single
test asserts all three results
(`test_only_these_two_retained_chapter_30_pages_print_more_than_one_rendition`):

1. **Rendition split.** The adapter's `_rendition_starts` counts the divs that
   open with the section number and a heading. Exactly two pages print more
   than one: §63-3022E and §63-3025D, two renditions each. The other 160 print
   one.
2. **Text markers.** A scan of every page's statute text for bracketed text
   containing "effective", "until", "repeal", "expire", "operative",
   "contingent", "terminat" or "null" finds only those two pages. Each carries
   exactly "[effective until January 1, 2027]" and "[effective January 1,
   2027]".
3. **Session laws.** The History notes cite six 2026 session laws: chapters 1,
   79, 81, 153, 184 and 302. Chapter 79 is cited only by §§63-3022E and
   63-3025D. Every section citing one of the other five prints one rendition.

The chapter page lists 162 sections, each once, all linked and all retained.

**Live checks.** On 2026-09-27 and on 2026-10-12 the adapter re-extracted the
chapter from legislature.idaho.gov into a scratch base. It ran over the network,
with that day as the expression date.

- **2026-10-12.** The output and comparison are in
  `evidence/live-2026-10-12/`.
  - It gave the same 166 citation paths, in the same order.
  - No row differs in heading, body, citation label, ordinal, parent, kind,
    level, legal identifier, identifiers or metadata. That includes both
    variant rows.
  - The raw bytes of all 165 pages differ from the 2026-09-14 retrieval. In
    `63-3022E.html` the six changed lines are inline-script lines that carry
    WordPress nonces.
- **2026-09-27.** The comparison gave the same result. Its scratch output was
  not kept through the 2026-10-12 host restart.

## What the two versions say

The marker on each page dates the change to January 1, 2027. The History notes
attribute it to 2026 Idaho Sess. Laws ch. 79: sec. 29 for §63-3022E and sec. 30
for §63-3025D. The two versions of each section are word-for-word identical
except for the marker and one cross-reference, which occurs twice, in (1) and
(4):

| in force until 2027-01-01 | effective 2027-01-01 |
|---|---|
| "as defined in subsection (5) of section 66-402 , Idaho Code" | "as defined in section 66-402 (4), Idaho Code" |

A test checks this: after that substitution and the marker's, the bodies are
equal (`test_the_two_versions_differ_only_in_the_marker_and_the_66_402_reference`).

The §66-402 page from legislature.idaho.gov, saved during this work on
2026-09-27 as `66-402-live-2026-09-27.html`, also prints two renditions. Its
History cites 2026 ch. 79, sec. 32.

- **Two definitions go.** The 2027 rendition drops the definitions of
  "Artificial life-sustaining procedures" and "Manage financial resources".
- **"Developmental disability" moves.** It goes from (5) to (4).
- **Its words stay the same.** Its four lines are identical in both renditions
  apart from that number.

§66-402 is not in the corpus.

## Convention

On `origin/main` eabe4ed94, neither convention the brief names has landed. On
2026-10-12 both PRs were open (`evidence/sibling-prs-*.txt`):
- #752, California LegInfo concurrent versions;
- #754, Maine "TEXT EFFECTIVE UNTIL / TEXT EFFECTIVE".

New Mexico, Vermont and Delaware use sibling variant segments on `origin/main`,
as `citation_segment.VARIANT_SEPARATOR` documents. One example is the released
`us-nm/statute/7-2F-2--effective-2027-01-01`. A variant is never a child
segment.

This change also supplies `metadata.variant` and
`metadata.canonical_citation_path`:
- New Mexico and Delaware supply them, and #752's proposed schema text (§4.0)
  requires them.
- Existing Vermont variant rows carry neither field.

**Agreement with #754.** Its descriptors for dated Maine versions are
`effective-until-<date>` and `effective-<date>`, the same form as here. It
keeps the version in force on the expression date at the plain path, as here.

**Difference from #752.** California gives every LegInfo version a variant
path, including the version at the plain path. LegInfo's picker makes the plain
path's version depend on the capture session. Idaho has no such dependence:
- the version at the plain path is a function of the page and the expression
  date;
- so a page with N renditions gives N rows here, as in NM, VT, DE and ME;
- and the plain row stays identical in content to the row both carriers hold.

**A version's variant path depends on the scope.** When an Idaho chapter is
extracted with an expression date on or after 2027-01-01, the 2027 text moves
to the plain path and the 2026 text moves to `--effective-until-2027-01-01`.
Citations to a variant should pin the scope.

### Fields

| field | plain row (in force on the expression date) | variant row |
|---|---|---|
| `citation_path`, `source_id` | `us-id/statute/63-3022E`, `63-3022E` | `…/63-3022E--effective-2027-01-01`, `63-3022E--effective-2027-01-01` |
| `id` | `deterministic_provision_id(citation_path)`, unchanged | the same function of the variant path |
| `citation_label`, `legal_identifier` | `Idaho Code § 63-3022E` | the same |
| `identifiers` | `{"idaho:title": "63", "idaho:chapter": "30", "idaho:section": "63-3022E"}` | the same |
| `heading` | the rendition's own heading | the rendition's own heading |
| `body` | from "[effective until January 1, 2027] (1) …" to the end of (4) | from "[effective January 1, 2027] (1) …" to the end of (4) |
| `parent_citation_path`, `level`, `ordinal`, `kind` | chapter 30, 2, the listing ordinal, `section` | the same as the plain row. #752 also repeats the plain row's ordinal; navigation then sorts the variant right after it by segment. |
| `source_url`, `source_path`, `source_format`, inventory `sha256` | the section page | the same page |
| `metadata.source_history` | the page's one History note | the same note: the page prints one History for both renditions |
| `metadata.references_to` | from its own rendition's text and links | from its own rendition's text and links |
| `metadata.variant` | absent | `effective-2027-01-01` |
| `metadata.canonical_citation_path` | absent | the plain path |
| `metadata.effective_note` | absent | `effective January 1, 2027` (the marker as printed) |
| `metadata.status` | as before (absent on these two) | see below |

**`metadata.status` on a variant row.** The adapter's own status takes
precedence. When it gives none, the marker sets the status:
- "effective" gives `future_or_conditional`;
- "until" gives `effective_until`.

The vocabulary is NM's, DE's, NV's and RI's. Both variant rows here are
`future_or_conditional`.

The variant row sits right after its plain row in the provisions and inventory
files.

**Naming rules for a non-primary rendition.**
- "[effective <date>]" gives `effective-<ISO date>`.
- "[effective until <date>]" gives `effective-until-<ISO date>`.
- A rendition with no marker gives `variant-<n>`, where n is its 1-based printed
  position (NM's fallback).

## Adapter change (`src/axiom_corpus/corpus/state_adapters/idaho.py`)

- **`parse_idaho_section_page`** keeps its signature and pre-change behaviour.
  - **One rendition or none.** The page is read whole. No expression date is
    required or validated, and no marker is parsed.
  - **Several renditions.** It first requires a valid expression date. Then it
    reads the first recognised effective marker in each rendition's opening
    div.
  - **Selection.** It selects the one dated rendition in force. If no dated
    rendition is in force, it selects the only unmarked rendition. Otherwise it
    raises the same `ValueError` as before.
  - The 2026-07-31 repro script and its test still call it unchanged.
- **`parse_idaho_section_versions`** (new) returns that same section first,
  then each other rendition in printed order as a variant.
  - **Variant content.** Each variant is the shared page prefix, its own span,
    and everything from the page's first History or notes marker on. So notes
    printed without a History reach every variant.
  - **The plain row's suffix is unchanged.** It still starts at the History
    marker after the last rendition. Without a History, the pre-change adapter
    gives such notes to the last printed rendition only, and the plain row
    keeps that reading.
- **Refusals.** It raises `IdahoRenditionError`, which carries the plain section
  unchanged, when a rendition cannot safely become a row:
  - a rendition opens after the page's first History or notes marker,
    wherever it is: a section heading quoted in a note or after a History, or
    any heading when a History or notes marker precedes the first one;
  - a rendition's marker is not the first thing after its heading (a marker
    quoted in the text);
  - two variants would share a name.
- **The extractor** keeps the plain row of a refused page, records the page in
  the report's `errors`, and emits no variant for it.
  - A refused page never loses a row the pre-change adapter produced, and it
    never passes silently.
  - No retained chapter 30 page is refused.
- **Helpers.**
  - `_rendition_starts` finds the spans.
  - `_section_renditions` reads each span's first recognised marker.
  - `_primary_rendition` applies the old selection rule.
  - `_apparatus_start` finds the page's first History or notes marker.
  - `_rendition_divs` assembles the shared page prefix, one rendition, then the
    suffix. The suffix starts at the History marker for the plain row and at
    `_apparatus_start` for variants.

  The span arithmetic and the selection rule are those of the removed
  `_select_section_rendition`.
- **`limit`** still counts section listings, not rows.
- **Metadata.** `_section_record` and `_section_inventory_item` add `variant`,
  `canonical_citation_path` and `effective_note` to variant rows only.
- **Default.** Variant rows are emitted by default, with no option, as the NM,
  DE, NJ, NV and RI adapters do. A page with one rendition extracts exactly as
  before.

**Callers.** These were found by text search:
- `cli.py` (`extract_idaho_statutes`);
- `scripts/repro/idaho_title_63_chapter_30_successor.py`;
- the tests.

GitNexus could not help (`evidence/gitnexus-2026-10-12.txt`):
- **`impact`** fails on this index, which is storage version 42 while the CLI
  reads 40.
- **`detect_changes`** reports the main clone's own checkout, not this
  worktree. It resolves no symbol.

## Extraction

Manifest `manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml`:

- **Source.** `source_dir` is the 2026-09-14 chapter scope's retained sources:
  the title index, the Title 63 page, the chapter 30 page and 162 section
  pages. They are fetched with `corpus fetch us-id`. The adapter reads them and
  never falls back to the network.
- **Dates.** `source_as_of` and `expression_date` stay 2026-09-14.
- **Filters.** `only_title` 63 and `only_chapter` 30.
- **Scope name.** The adapter appends `-us-id-title-63-chapter-30` to the
  version.

```bash
uv run axiom-corpus-ingest corpus fetch us-id
uv run axiom-corpus-ingest extract-state-statutes --base data/corpus \
  --manifest manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml
```

**Result:**
- 166 provisions: 1 title, 1 chapter and 164 section rows (162 sections and 2
  variants);
- 165 source files;
- 0 errors;
- coverage complete.

The 165 source files are byte-identical to the 2026-09-14 scope's and match
that scope's locked SHA-256 values. So the new lock's source entries name the
same content-addressed objects.

## Rows

| citation path | id | body characters |
|---|---|---:|
| `us-id/statute/63-3022E` | `245b3887-445d-5f57-8150-9c9b31161700` (unchanged) | 1,331 |
| `us-id/statute/63-3022E--effective-2027-01-01` | `1efe3646-4b77-5409-bfb9-1d7610f8c5de` | 1,295 |
| `us-id/statute/63-3025D` | `bddf405d-43b2-5c4e-9d1c-35ba0f7db1e3` (unchanged) | 1,499 |
| `us-id/statute/63-3025D--effective-2027-01-01` | `6f3cbe19-34cf-5ed3-8ca5-d174a1438066` | 1,463 |

Retained pages:
- `63-3022E.html`, SHA-256 `87dc6b02…9865bd`;
- `63-3025D.html`, SHA-256 `adfc1391…59ea71`.

## Invariants (stated and executed)

In `tests/test_corpus_idaho.py`:

1. **Single-row API, differential.** `parse_idaho_section_page` equals
   `origin/main`'s, error for error with identical messages.
   - **The oracle.** The test's oracle copies three function bodies from that
     commit: `parse_idaho_section_page`, `_select_section_rendition` and
     `_rendition_effective_marker`. Only the helper and regex names are renamed
     and the signature annotations dropped. The helpers they call are unchanged
     on this branch.
   - **Generated pages.** 500 Hypothesis pages run per run. Each page has one
     to four renditions. Each rendition has no marker, "[effective <date>]",
     "[effective until <date>]" or an impossible date, and the marker leads the
     text or sits inside it.
   - **Page extras.** A page may also have an unheaded prefix line, a History,
     notes, a heading quoted after notes or after a bare History, or notes
     before the first heading.
   - **Expression dates.** These are valid, missing or malformed.
   - **Exhaustive grid.** It adds 155 pages for each of four expression-date
     inputs: 2026-09-14, 2027-01-01, a missing date and a malformed one. The
     pages have one to three renditions with five marker choices each.
2. **The plain row never moves.** `parse_idaho_section_versions` does one of
   three things: raises the same error, returns that section first, or raises
   `IdahoRenditionError` carrying exactly that section.
3. **Refusals.** It refuses only in three cases, and the modelled cases are
   refused:
   - a rendition after the page's first History or notes marker;
   - a marker inside the text;
   - a shared name.
4. **Selection.** On well-formed pages the plain row is the one rendition a
   model of the markers says is in force. A page with one rendition is read
   whole.
5. **Conservation on accepted, well-formed pages.**
   - Each printed rendition becomes exactly one section.
   - Variants follow the plain one in printed order.
   - Each variant has its own heading and body and the page's History.
   - A second generator builds 300 pages per run with exactly one rendition in
     force by construction. All of them have one to three variants.
6. **Naming.** Variant names follow the markers. They give sibling paths that
   match the citation-path grammar, and their `canonical_citation_path` is the
   plain path.
7. **Status.** A dated variant is never in force on the expression date, and
   its `effective_note` follows its marker. The generated text contains no
   status-triggering words, so its `status` is the marker's:
   `effective_until` or `future_or_conditional`.
8. **Determinism.** Parsing twice gives equal results.
9. **`limit`.** It counts sections, not variant rows. A limited extraction over
   two chapters, with the variant in the first, still reaches the second.
10. **Refused pages.** A refused page keeps its plain row, adds no variant, and
    appears in `errors`.
11. **Shared notes.** Every variant carries the page's notes, with or without a
    History. The plain row carries them as the pre-change adapter does: always
    after a History, and otherwise only when it is the last rendition.
12. **Mutations.** Four mutations of these rules were applied one at a time, and
    each made at least one test fail (`evidence/mutations-4272acab5.txt`):
    - counting variant rows against `limit`;
    - dropping History from `_apparatus_start`;
    - scanning for it only after the first heading;
    - giving variants the History-only suffix.

In `tests/test_us_id_title_63_chapter_30_concurrent_versions.py`, on the
fetched bytes:

13. **Replay.** `extract-state-statutes` runs with the committed manifest, its
    options and its `source_dir`, with `requests.get` patched to fail.
    - It rebuilds the provisions, inventory and coverage byte for byte.
    - All 165 rebuilt sources equal this scope's and the 2026-09-14 retained
      ones.
    - A change to the manifest's options fails this test.
14. **Differential against the chapter carrier.**
    - Every one of its 164 rows is present, in the same order.
    - Each is equal in every field except `version` and `source_path`.
    - The only additions are the two variants, each right after its plain row.
15. **Differential against the 2026-07-31 carrier.** The test checks the seven
    carried rows: heading, body, citation label, legal identifier,
    identifiers, kind, level and parent, plus each section row's metadata.
    Inspection of the data finds that the rest differ only in provenance and
    placement:
    - `version` and `source_path`;
    - `source_url`. That scope used the 2026-07-13 retrieval's URLs, with its
      title and chapter rows pointing at the §63-3022D page. Here they are the
      title index, Title 63, chapter 30 and section URLs of the 2026-09-14
      retrieval.
    - `source_format` of the title and chapter rows;
    - `source_as_of` and `expression_date`: 2026-07-13 there;
    - ordinals: that scope numbered its title and chapter rows 1 and its five
      sections 1 to 5;
    - the chapter row's `metadata.chapter_pdf_url`, present here;
    - the inventory's `container_source` note on its title and chapter rows.
16. **Variant rows.** Each variant shares these fields with its plain row:
    parent path and parent id, level, ordinal, kind, heading, citation label,
    legal identifier, identifiers, source URL, source path and source format.
    Also:
    - its `source_id` is its variant segment;
    - its id differs from the plain row's;
    - its body begins with the 2027 marker;
    - its `source_history`, `references_to`, section, title and chapter
      metadata equal the plain row's.
17. **Versions differ only in the reference.** The two versions of each
    section differ only as described under "What the two versions say".
18. **Completeness.** The three readings under "The whole chapter".
19. **No stray variants.** Every carrier of a `--` path in the us-id provisions
    is collected. The two variant paths have exactly one carrier, this scope,
    and no other `--` path exists.
20. **Release.** At each line head, this scope stands in for the head's chapter
    30 carrier.
    - The head's us-id scopes of every document class, with the swap, validate
      with strict warnings and 0 issues.
    - The scope keeps every citation path the replaced scope carried.
    - A pin test checks the heads: among selectors that carry one of the two
      existing chapter 30 carriers, those that no selector names as its
      predecessor. The predecessor is the first `us-rulespec-…` name in each
      `description`.

## rulespec-us

rulespec-us `origin/main` 4b35d0872 (2026-10-12) encodes both sections. None of
these files has changed since 54d90a725 (2026-09-25):
- `us-id/statutes/63-3022E.yaml`;
- `us-id/statutes/63-3025D.yaml`;
- the 2026 policy hold `us-id/policies/income_tax/2026_full_year_resident_source_hold.yaml`,
  whose rules citing them run 2026-01-01 to 2026-12-31.

**The 2027 version changes no encoded parameter.** Each module's parameters and
their proof excerpts, checked against both versions' bodies in this scope:

| module | parameter | value | excerpt in the 2026 text | in the 2027 text |
|---|---|---:|---|---|
| 63-3022E | `per_qualifying_individual_deduction_amount` | 1000 | yes | yes |
| 63-3022E | `maximum_deductions_per_return` | 3 | yes | yes |
| 63-3022E | `qualifying_age_threshold` | 65 | yes | yes |
| 63-3022E | `support_fraction_threshold` | 1 / 2 | yes | yes |
| 63-3025D | `family_member_payment_amount` | 100 | yes | yes |
| 63-3025D | `self_filing_developmental_disability_credit_amount` | 100 | yes | yes |
| 63-3025D | `elderly_family_member_age_threshold` | 65 | yes | yes |
| 63-3025D | `household_payment_support_fraction_threshold` | 1 / 2 | yes | yes |
| 63-3025D | `maximum_household_member_payments_per_calendar_year` | 3 | yes | yes |

**No condition changes either.** The derived rules' conditions read the same in
both versions: the household, the immediate family member, age or
developmental disability, more than half of support, and the filer exception.
The definition the sections cite has the same words in both renditions of
§66-402.

**Two input names will read as stale.** In `63-3025D.yaml`, two inputs name
§66-402(5):
- `family_member_has_developmental_disability_as_defined_in_section_66_402_5`;
- `person_has_developmental_disability_as_defined_in_section_66_402_5`.

From 2027-01-01 the definition is §66-402(4). The meaning is the same, so the
TY2026 values are unaffected. A TY2027 encoding would cite the
`--effective-2027-01-01` rows and might rename the inputs. `63-3022E.yaml`
names its input `person_has_developmental_disability`, with no subsection.

**Version dates.** Every version in both modules is `effective_from:
'0001-01-01'`, with no end date. Nothing in the 2027 text requires a new
version.

## Release selection (not done here)

This PR adds no selector and edits none. The cut, which needs Max's call, would
put this scope in place of the chapter 30 carrier in a successor of each line
head.

On `origin/main` eabe4ed94, three selectors carry a chapter 30 carrier and are
heads: no other selector names them as its predecessor in its `description`.

| line head | chain (from `us-rulespec-2026-08-08-obbb-alien-snap`) | carries | swap |
|---|---|---|---|
| `us-rulespec-2026-10-11-w5-remainder-union` | obbb → cutover-surface → canada-338 → program-ingestion → followup → federal-and-plans → cms-state-plans → wave4 → wave4-r2 → `2026-10-07-w6-bundle-gaps-union` → this | the chapter scope, and `2026-10-06-w6-income-tax-statute-id` | the chapter scope only; the w6 scope (Idaho Code §57-1110 and session-law documents) stays |
| `us-rulespec-2026-09-24-irs-sales-tax-tables-union` | obbb → cutover-surface → canada-338 → this | the 2026-07-31 successor | the successor |
| `us-rulespec-2026-09-24-snap-fy2027-cola` | obbb → this | the 2026-07-31 successor | the successor |

- **Effect on the w5-remainder head.**
  - The two variant rows are added.
  - Every row of the chapter scope is otherwise equal, apart from `version`
    and `source_path`.
- **Effect on the other two heads.**
  - All seven paths of the 2026-07-31 successor keep their text. This includes
    every chapter 30 path that rulespec-us's encoded modules cite: §§63-3022D,
    63-3022E, 63-3024, 63-3024A and 63-3025D.
  - The swap adds the other 157 chapter 30 sections and the two variants.
  - Rows move from `expression_date` 2026-07-13 to 2026-09-14.

The release test validates the Idaho slice of all three swaps.

## Review

### Round 1 (2026-09-27, on the pre-locks branch at fd3c7b64b)

Three Subfleet review jobs ran on GPT-6 Astra (`evidence/subfleet-jobs.jsonl`).
Their reports are in `~/reviews/axiom-corpus-id-concurrent-versions/`.

- **Adversarial review** (`out-adversarial.md`): REQUEST CHANGES. It confirmed
  the data:
  - both variant bodies;
  - all 164 chapter-scope rows;
  - the 165 source hashes;
  - the July carrier's seven rows;
  - identical output with 1 and 4 workers.

  It raised four code findings and noted that signing was still pending. The
  code findings are addressed as follows; signing is the last step of this
  work.

  | finding | disposition |
  |---|---|
  | A section heading quoted in a compiler's note became a variant row (blocker) | Refused: a rendition after the page's first History or notes marker raises `IdahoRenditionError`; the plain row is kept and the page reported. Test `test_a_section_heading_quoted_in_a_note_is_never_a_variant`. |
  | The single-row API raised on name collisions where `main` returned a row, and parsed markers before checking the date | `parse_idaho_section_page` is again `main`'s logic, with checks in `main`'s order. Collisions are refused only by the all-renditions API, which keeps the plain row. Tests `test_two_renditions_with_one_name_keep_the_plain_row_and_report_the_page`, `test_date_checks_come_before_marker_parsing`, and the exhaustive grid. |
  | `hypothesis` missing from `uv.lock` | Moot. `main` has since added `hypothesis>=6.168.3` to the dev extra and `uv.lock`, and this branch no longer touches either. |
  | Tests claimed more than they checked: a shared-helper oracle; no notes or malformed dates; a `limit` mutation survived; the release check used one scope; the variant scan overwrote carriers | The oracle is now `main`'s parser bodies (invariant 1). The generators add notes, quoted headings, quoted markers, prefixes, and impossible, missing or malformed dates. The `limit` mutation now fails a test (invariant 12). The release test runs on each head's us-id scopes. The variant scan collects every carrier. |
  | A marker quoted inside an unmarked rendition named a variant (boundary note) | Refused: the marker must lead the text. Test `test_a_quoted_marker_never_names_a_variant`. |

- **Independent re-implementation** (`out-reimplementation.md`). It wrote its
  own parser from a written specification, without reading the adapter or the
  tests.
  - Every citation path, path order, heading, body, history and variant field
    matched.
  - Its mutation checks caught a body swap and dropped variants.
  - Its only mismatches were `metadata.status` on three unchanged plain rows.
    §§63-3049 and 63-3065 are "expired" and §63-3079 ("Franchise tax not
    repealed") is "repealed".

  None of those passages declares its own section expired or repealed. The
  adapter's `_section_status` matches those words anywhere in the heading,
  body, History or notes. The rows carry the same status in the 2026-09-14
  scope, and this PR keeps plain rows identical, so the fix is a separate
  change (follow-up 1).
- **Claim audit** (`out-claim-audit.md`) was blocked before it inspected
  anything. Its brief forbade commands, so the lane could not read files. It
  was rerun in round 2.

### Round 2 (2026-10-12, at 374666c2d)

Two Subfleet review jobs ran on GPT-6.1 Sol. Their reports are in `round2/`.

- **Adversarial review** (`round2/out-review.md`): REQUEST CHANGES.
  - **Round-1 fixes confirmed.**
    - The single-row API: 3,905 probes against the actual base adapter, with
      zero differences.
    - The order of the date checks.
    - The oracle and generators.
    - `limit`, the release check and the variant scan.
  - **Also confirmed correct.**
    - All 164 rows and both variant bodies, from its own parse of the HTML.
    - All 165 sources and 166 inventory hashes.
    - Identical output with 1 and 4 workers.
    - The three line heads and their chains. Each swapped us-id slice
      validated strictly with 0 errors and 0 warnings.
  - **New findings, all addressed in e600c5632:**

  | finding | disposition |
  |---|---|
  | A History or notes marker before the first section heading let a later heading become a variant (blocker) | No rendition may open after the page's first History or notes marker, wherever it is. Test `test_history_or_notes_before_the_first_heading_refuse_every_variant`. |
  | Notes printed without a History did not reach earlier variants | Variants share everything from the first History or notes marker on; the plain row keeps the pre-change suffix. Test `test_notes_printed_without_a_history_are_shared_by_every_variant`, plus notes in the well-formed generator. |
  | No test would catch dropping History from the refusal | Test `test_a_section_heading_quoted_after_a_bare_history_is_never_a_variant`. The generators quote headings after a bare History and put notes before the first heading. Each mutation in invariant 12 is caught. |
  | The replay test did not read the manifest | It runs `extract-state-statutes` with the committed manifest. |
  | The note described signing before it happened; "git-tracked" in the manifest comment; the July differences were incomplete | The signing statements describe the signing commit as a step still to come. The manifest comment is corrected. The July differences are listed in full (invariant 15). |

  It also restated three behaviours of the single-row API that this PR keeps as
  the base adapter has them:
  - separate History notes combine on the plain row;
  - an unheaded prefix line takes the heading slot;
  - the three status values of follow-up 1.
- **Claim audit** (`round2/out-claim-audit.md`): CORRECTIONS NEEDED. Every
  correction is applied in this note:
  - **Signing and lock.** Described as the signing commit's steps.
  - **Selection mechanism.** Stated exactly.
  - **Status precedence.** The adapter's own status comes first.
  - **`identifiers`.** Their own table row, and now checked by the July test.
  - **Vermont.** It does not carry the variant metadata.
  - **Test descriptions.** Kept to what each test checks; tested facts are
    separated from data inspection.
  - **rulespec-us.** "Cites" narrowed to its encoded modules, because
    `bulk/worklist.yaml` also names §§63-3029L, 63-3022A and 63-3022H.
  - **The w5-remainder head.** Its effect is stated exactly.
  - **The pin test.** Its predicate is described.
  - **Unrecorded claims.** The external facts the audit could not check offline
    now cite recorded evidence. These are the 2026-10-12 live check, the PR
    states, the Subfleet job metadata, the GitNexus output and the mutation
    results. The 2026-09-27 live check is marked as not kept.
  - **Completeness scans.** The text-marker and session-law scans it flagged as
    unrecorded are now asserted by the completeness test.

## Follow-ups (not in this PR)

1. **Idaho status heuristic.** `_section_status` should mark only a section's
   own status. This affects §§63-3049, 63-3065 and 63-3079 in this chapter. It
   is proposed as a separate task (task_b0651036).
2. **Schema text.** When #752 merges, add an Idaho row to the variants table in
   `schema/citation-path.v1.md` §4.0: `us-id/statute/63-3022E--effective-2027-01-01`.
3. **Ratchet merge order.** This PR raises `uppercase_segments` from 18,796 to
   18,798. The two variant paths keep Idaho's capital section suffixes (E, D).
   Any other open PR that raises the same baseline must re-measure it after the
   first of them merges.
4. **rulespec-us.** At the TY2027 encoding of §§63-3022E and 63-3025D:
   - cite the `--effective-2027-01-01` rows, or the plain rows of a scope
     extracted on or after 2027-01-01;
   - consider renaming the two `…_66_402_5` inputs.
5. **§66-402.** Idaho Code Title 66 is not in the corpus. The
   developmental-disability definition is an input in rulespec-us today.

## Checks

These were recorded at 4272acab5 in `evidence/local-checks-4272acab5.txt`. That
is the last commit before this note's final edit; the commits after it change
only this note. The worktree was clean, with every locked provisions file and
the us-id scopes fetched.

- `ruff check .`: all checks passed.
- `mypy src/axiom_corpus/corpus --ignore-missing-imports`: no issues in 98
  source files.
- `towncrier check --compare-with origin/main`: finds
  `changelog.d/us-id-statute-concurrent-versions.added.md`.
- `pytest` with `AXIOM_CORPUS_PARTIAL_TESTS=1`, serial, over five files: 144
  passed. The files are `tests/test_corpus_idaho.py`,
  `tests/test_us_id_title_63_chapter_30_concurrent_versions.py`,
  `tests/test_idaho_statute_successor.py`, `tests/test_citation_segment.py` and
  `tests/test_corpus_cli.py`.
- Hypothesis: 500 passing examples for `test_idaho_rendition_invariants` and
  300 for `test_well_formed_pages_keep_every_rendition`, with 0 failing.
- `scripts/validate_citation_paths.py`: OK, with `uppercase_segments` at
  18,798 / 18,798 over 507,658 unique paths.
- Mutations: four, each caught (`evidence/mutations-4272acab5.txt`).

The full suite needs every corpus scope fetched. CI runs it on the pull request,
and its result is recorded on the PR, not here.

## Certification

The ingest manifest attests this note as its reasoning log by SHA-256. It is
signed after the last edit to this note, from the clean content commit. The
ingest key is supplied to the signer in the environment, read from the agent
secret store. Signing also writes the scope's lock file and uploads its missing
objects:

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus \
  --jurisdiction us-id --document-class statute \
  --version 2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30 \
  --command "uv run axiom-corpus-ingest extract-state-statutes --base data/corpus --manifest manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml" \
  --reasoning-log docs/ingest-runs/2026-09-27-id-title-63-chapter-30-concurrent-versions.md \
  --lock --push
```
