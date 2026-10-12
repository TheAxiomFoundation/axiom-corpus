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

It was re-extracted offline from the 165 pages the 2026-09-14 scope retained.
Its bytes live outside git, pinned by the lock file
`.axiom/corpus-locks/us-id/statute/2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30.json`
(`docs/corpus-storage.md`), and it carries a signed ingest manifest. It is not
published, loaded into Supabase or added to a release selector. Its own
content-addressed objects are uploaded to R2 `objects/sha256/`, which
publishes nothing (AGENTS.md).

The work started on 2026-09-27 on `origin/main` f1916d73b. It was rebuilt on
2026-10-12 on `origin/main` eabe4ed94, after the switch that moved corpus bytes
into lock files (b33d5bf08). The extraction is byte-identical on both bases.

## The whole chapter

All 162 section pages the chapter scope retained were read, three ways:

1. **Rendition split.** The adapter's `_rendition_starts` counts the divs that
   open with the section number and a heading. Exactly two pages print more
   than one: §63-3022E and §63-3025D, two renditions each. The other 160 print
   one. A test pins this
   (`test_only_these_two_retained_chapter_30_pages_print_more_than_one_rendition`).
2. **Text markers.** A scan of every page's statute text for bracketed
   "effective", "until", "repeal", "expire", "operative", "contingent",
   "terminat" or "null" markers finds only the four markers on those two
   pages.
3. **Session laws.** The History notes cite six 2026 session laws: chapters 1,
   79, 81, 153, 184 and 302. Only chapter 79 (secs. 29 and 30) amends a
   chapter 30 section with a delayed effective date printed as a second
   rendition. The sections the other five amend print one rendition.

The chapter page lists 162 sections, each once, all linked and all retained.

**Live checks.** On 2026-09-27 and again on 2026-10-12 the adapter
re-extracted the chapter from legislature.idaho.gov (network, with that day as
the expression date) into a scratch base.
- Both runs gave the same 166 citation paths, in the same order, as this
  scope.
- Every row had the same heading, body, label, ordinal, parent, identifiers and
  metadata, including both variant rows.
- The raw bytes of all 165 pages differ from the 2026-09-14 retrieval. In
  `63-3022E.html` the six changed lines are WordPress nonces in inline scripts.
- No difference reaches an extracted row: no row of the chapter changed between
  2026-09-14 and 2026-10-12.

## What the two versions say

2026 Idaho Sess. Laws ch. 79 amends both sections (sec. 29 for §63-3022E,
sec. 30 for §63-3025D), effective January 1, 2027. The two versions of each
section are word-for-word identical except for the marker and one
cross-reference, which occurs twice, in (1) and (4):

| in force until 2027-01-01 | effective 2027-01-01 |
|---|---|
| "as defined in subsection (5) of section 66-402 , Idaho Code" | "as defined in section 66-402 (4), Idaho Code" |

A test checks this: after that substitution and the marker's, the bodies are
equal (`test_the_two_versions_differ_only_in_the_marker_and_the_66_402_reference`).

The same act amends §66-402 (sec. 32). The live §66-402 page fetched on
2026-09-27 prints two renditions too. In the 2027 text the definitions of
"Artificial life-sustaining procedures" and "Manage financial resources" are
gone, so "Developmental disability" moves from (5) to (4). Its four lines of
text are identical in both renditions apart from that number. §66-402 is not
in the corpus; the fetched page is kept at
`~/reviews/axiom-corpus-id-concurrent-versions/66-402-live-2026-09-27.html`.

## Convention

Neither convention the brief names has landed: #752 (CA LegInfo concurrent
versions) and #754 (ME "TEXT EFFECTIVE UNTIL / TEXT EFFECTIVE") were both
still open on 2026-10-12. The convention on `origin/main` is New Mexico's,
Vermont's and Delaware's, the one `citation_segment.VARIANT_SEPARATOR`
documents:

- A dated same-number version is a sibling segment `<section>--effective-YYYY-MM-DD`,
  e.g. the released `us-nm/statute/7-2F-2--effective-2027-01-01`. It is never a
  child segment.
- The variant row carries `metadata.variant` and `metadata.canonical_citation_path`.

This change follows it. Both open PRs agree on the parts that matter here:

- **Slug.** #754's descriptors for dated Maine versions are `effective-until-<date>`
  and `effective-<date>`, the same form as here.
- **Plain path.** #754 keeps the version in force on the expression date at the
  plain path, as here.
- **Metadata.** #752's schema text (§4.0) requires `variant` and
  `canonical_citation_path`.

The one choice that differs from #752 is whether the in-force version also gets
a variant path. California gives every LegInfo version one, including the
version at the plain path, because LegInfo's picker makes the plain path's
version depend on the capture session. Idaho has no such dependence: the
version at the plain path is a function of the page and the expression date. So
a page with N renditions gives N rows here, as in NM, VT, DE and ME, and the
plain row stays identical in content to the row both carriers hold.

A consequence: when an Idaho chapter is extracted with an expression date on
or after 2027-01-01, the 2027 text moves to the plain path and the 2026 text to
`--effective-until-2027-01-01`. The variant path of a version depends on the
scope's expression date, so citations to a variant should pin the scope.

### Fields

| field | plain row (in force on the expression date) | variant row |
|---|---|---|
| `citation_path`, `source_id` | `us-id/statute/63-3022E`, `63-3022E` | `…/63-3022E--effective-2027-01-01`, `63-3022E--effective-2027-01-01` |
| `id` | `deterministic_provision_id(citation_path)`, unchanged | the same function of the variant path |
| `citation_label`, `legal_identifier`, `identifiers` | Idaho Code § 63-3022E | the same: it is the same section |
| `heading` | the rendition's own heading | the rendition's own heading |
| `body` | from "[effective until January 1, 2027] (1) …" to the end of (4) | from "[effective January 1, 2027] (1) …" to the end of (4) |
| `parent_citation_path`, `level`, `ordinal`, `kind` | chapter 30, 2, the listing ordinal, `section` | the same as the plain row (#752 also repeats the plain row's ordinal; navigation then sorts the variant right after it by segment) |
| `source_url`, `source_path`, `source_format`, inventory `sha256` | the section page | the same page |
| `metadata.source_history` | the page's one History note | the same note: the page prints one History for both renditions |
| `metadata.references_to` | from its own rendition's text and links | from its own rendition's text and links |
| `metadata.variant` | absent | `effective-2027-01-01` |
| `metadata.canonical_citation_path` | absent | the plain path |
| `metadata.effective_note` | absent | `effective January 1, 2027` (the marker as printed) |
| `metadata.status` | as before (absent on these two) | `future_or_conditional`; an expired "until" variant would be `effective_until`. The vocabulary is NM's, DE's, NV's and RI's. |

The variant row sits right after its plain row in the provisions and inventory
files.

**Naming rules for a non-primary rendition.**
- "[effective <date>]" gives `effective-<ISO date>`.
- "[effective until <date>]" gives `effective-until-<ISO date>`.
- A rendition with no marker gives `variant-<n>`, where n is its 1-based printed
  position (NM's fallback).

## Adapter change (`src/axiom_corpus/corpus/state_adapters/idaho.py`)

- **`parse_idaho_section_page`** keeps its signature and behaviour exactly. It
  returns the rendition in force on the expression date, through the same
  checks in the same order as before: the date must be given and valid, then
  every marker must parse, then exactly one rendition must be in force. The
  2026-07-31 repro script and its test use it unchanged.
- **`parse_idaho_section_versions`** (new) returns that same section first,
  then each other rendition in printed order as a variant.
- **Refusals.** It raises `IdahoRenditionError`, which carries the plain section
  unchanged, when a rendition cannot safely become a row:
  - a rendition opens after the page's History or notes begin (a section
    heading quoted in a compiler's note);
  - a rendition's marker is not the first thing after its heading (a marker
    quoted in the text);
  - two variants would share a name.
- **The extractor** keeps the plain row of a refused page, records the page in
  the report's `errors`, and emits no variant for it. A refused page therefore
  never loses a row the pre-change adapter produced, and it never passes
  silently. No retained chapter 30 page is refused.
- **Helpers.**
  - `_rendition_starts` finds the spans.
  - `_section_renditions` reads each span's marker.
  - `_primary_rendition` applies the old selection rule.
  - `_rendition_divs` assembles the shared page prefix, one rendition, then the
    shared History and notes.
  - `_apparatus_start` finds the first History or notes marker.

  The span arithmetic and the selection rule are those of the removed
  `_select_section_rendition`.
- **Pages with one rendition** are still read whole, and their markers are still
  never parsed.
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

GitNexus could not help:
- `impact` fails on this checkout's index (storage version 42; the CLI reads
  40, as #754 found).
- `detect_changes` reads the main clone, not the worktree.

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

The 165 source files are byte-identical to the 2026-09-14 scope's, so their
lock entries name the same R2 objects. The provisions, inventory and coverage
are byte-identical to the extraction made on f1916d73b before the rebuild.

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

1. **Differential, single-row API.** `parse_idaho_section_page` equals
   `origin/main`'s, error for error with identical messages.
   - The oracle in the test is that commit's `parse_idaho_section_page`,
     `_select_section_rendition` and `_rendition_effective_marker`, copied
     verbatim. The helpers they call are unchanged on this branch.
   - It runs over 500 Hypothesis pages per run. Each page has one to four
     renditions, with no marker, "[effective <date>]", "[effective until
     <date>]" or an impossible date, led by the marker or with it inside the
     text.
   - Pages may also carry an unheaded prefix line, a History, and a compiler's
     note that may quote the section heading.
   - The expression date is valid, missing or malformed.
   - An exhaustive grid adds 155 pages per expression date: one to three
     renditions, five marker choices each, at four dates.
2. **The plain row never moves.** `parse_idaho_section_versions` does one of
   three things: raises the same error, returns that section first, or raises
   `IdahoRenditionError` carrying exactly that section.
3. **Refusals.** It refuses only for a rendition after the History or notes, a
   marker inside the text, or a shared name. The modelled cases are refused.
4. **Selection.** On well-formed pages the plain row is the one rendition a
   model of the markers says is in force. A page with one rendition is read
   whole.
5. **Conservation.** Each printed rendition is exactly one section. Variants
   follow the plain one in printed order, each with its own heading and body
   and the page's History. A second generator builds 300 pages per run with
   exactly one rendition in force by construction, and all of them have one to
   three variants.
6. **Naming.** Variant names follow the markers. They give sibling paths that
   match the citation-path grammar, and their `canonical_citation_path` is the
   plain path.
7. **Status.** A dated variant is never in force on the expression date. Its
   `status` and `effective_note` follow its marker.
8. **Determinism.** Parsing twice gives equal results.
9. **`limit`.** It counts sections, not variant rows. A limited extraction over
   two chapters, with the variant in the first, still reaches the second.
10. **Refused pages.** A refused page keeps its plain row, adds no variant, and
    appears in `errors`.

In `tests/test_us_id_title_63_chapter_30_concurrent_versions.py`, on the
fetched bytes:

11. **Replay.** The manifest's parameters, run with `requests.get` patched to
    fail, rebuild the provisions, inventory and coverage byte for byte. All
    165 sources equal the committed ones and the 2026-09-14 retained ones.
12. **Differential against the chapter carrier.** Every one of its 164 rows is
    present, in the same order, equal in every field except `version` and
    `source_path`. The only additions are the two variants, each right after
    its plain row.
13. **Differential against the 2026-07-31 carrier.** Its seven rows are
    present, with the same heading, body, label, identifiers, kind, level and
    parent. Each section row also has the same metadata. What differs:
    - ordinals: that scope numbered its five sections 1 to 5;
    - the chapter row's `chapter_pdf_url`;
    - `expression_date`: 2026-07-13 there.
14. **Variant rows.** Each variant row shares every placement and source field
    with its plain row, has its own id, and begins with the 2027 marker.
15. **Versions differ only in the reference.** The two versions of each
    section differ only as described under "What the two versions say".
16. **Completeness.** Only §§63-3022E and 63-3025D of the 162 retained pages
    print more than one rendition, two each.
17. **No stray variants.** No other us-id scope carries a `--` path. Every
    carrier of each variant path is collected.
18. **Release.** In place of each line head's chapter 30 carrier, the scope
    validates with strict warnings and 0 issues. The check runs on the head's
    us-id scopes of every document class, and the scope keeps every citation
    path the replaced scope carried. A pin test fails if a new line head
    carries a chapter 30 carrier.

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

**No condition changes either.** The derived rules' conditions (household,
immediate family member, age or developmental disability, more than half of
support, the filer exception) read the same in both versions. The definition
the sections cite has the same words in both versions of §66-402.

**Two input names will read as stale.** In `63-3025D.yaml`, the inputs
`family_member_has_developmental_disability_as_defined_in_section_66_402_5` and
`person_has_developmental_disability_as_defined_in_section_66_402_5` name
§66-402(5). From 2027-01-01 the definition is §66-402(4). The meaning is the
same, so the TY2026 values are unaffected. A TY2027 encoding would cite the
`--effective-2027-01-01` rows and might rename the inputs. `63-3022E.yaml` names
its input `person_has_developmental_disability`, with no subsection.

**Version dates.** Every version in both modules is `effective_from:
'0001-01-01'`, with no end date. Nothing in the 2027 text requires a new
version.

## Release selection (not done here)

This PR adds no selector and edits none. The cut, queued for Max, would put
this scope in place of the chapter 30 carrier in a successor of each line head.

On `origin/main` eabe4ed94, three selectors carry a chapter 30 carrier and are
heads: no other selector names them as its predecessor in its `description`.

| line head | chain (from `us-rulespec-2026-08-08-obbb-alien-snap`) | carries | swap |
|---|---|---|---|
| `us-rulespec-2026-10-11-w5-remainder-union` | obbb → cutover-surface → canada-338 → program-ingestion → followup → federal-and-plans → cms-state-plans → wave4 → wave4-r2 → `2026-10-07-w6-bundle-gaps-union` → this | the chapter scope, and `2026-10-06-w6-income-tax-statute-id` | the chapter scope only; the w6 scope (Idaho Code §57-1110 and session laws) stays |
| `us-rulespec-2026-09-24-irs-sales-tax-tables-union` | obbb → cutover-surface → canada-338 → this | the 2026-07-31 successor | the successor |
| `us-rulespec-2026-09-24-snap-fy2027-cola` | obbb → this | the 2026-07-31 successor | the successor |

- **Effect on the w5-remainder head.** The two variant rows are added; every
  other row is the same.
- **Effect on the other two heads.**
  - All seven paths of the 2026-07-31 successor keep their text. This includes
    every chapter 30 path rulespec-us cites: §§63-3022D, 63-3022E, 63-3024,
    63-3024A, 63-3025D.
  - The swap adds the other 157 chapter 30 sections and the two variants.
  - Rows move from `expression_date` 2026-07-13 to 2026-09-14.

The release test validates all three swaps. The pin test fails if the set of
heads changes.

## Review

### Round 1 (2026-09-27, on the pre-locks branch at fd3c7b64b)

Three Subfleet jobs (`~/reviews/axiom-corpus-id-concurrent-versions/`):

- **Adversarial review** (Astra, `out-adversarial.md`): REQUEST CHANGES. It
  confirmed the data:
  - both variant bodies;
  - all 164 chapter-scope rows;
  - the 165 source hashes;
  - the July carrier's seven rows;
  - identical output with 1 and 4 workers.

  It raised four code findings and noted that signing was still pending. All
  are addressed:

  | finding | disposition |
  |---|---|
  | A section heading quoted in a compiler's note became a variant row (blocker) | Refused: a rendition after the History or notes raises `IdahoRenditionError`; the plain row is kept and the page reported. Test `test_a_section_heading_quoted_in_a_note_is_never_a_variant`. |
  | The single-row API raised on name collisions where `main` returned a row, and parsed markers before checking the date | `parse_idaho_section_page` is again `main`'s logic, checks in `main`'s order; collisions are refused only by the all-renditions API, keeping the plain row. Tests `test_two_renditions_with_one_name_keep_the_plain_row_and_report_the_page`, `test_date_checks_come_before_marker_parsing`, the exhaustive grid. |
  | `hypothesis` missing from `uv.lock` | Moot: `main` added `hypothesis>=6.168.3` to the dev extra and `uv.lock` since; this branch no longer touches either. |
  | Tests claimed more than they checked: a shared-helper oracle, no notes or malformed dates, a limit mutation that survived, a release check on one scope, the variant scan overwrote carriers | The oracle is now `main`'s whole parser, copied verbatim. The generators add notes, quoted headings, quoted markers, prefixes, impossible dates and missing or malformed dates. Two new tests cover a two-chapter `limit` (the mutation now fails) and refused pages. The release test runs on each head's us-id scopes. The variant scan collects every carrier. |
  | A marker quoted inside an unmarked rendition named a variant (boundary note) | Refused: the marker must lead the text. Test `test_a_quoted_marker_never_names_a_variant`. |

- **Independent re-implementation** (Astra, `out-reimplementation.md`) wrote
  its own parser from a written specification, without reading the adapter or
  the tests. All citation paths, path order, headings, bodies, histories and
  variant metadata matched, and its mutation checks caught a body swap and
  dropped variants. Its only mismatches were `metadata.status` on three
  unchanged plain rows: §63-3049 and §63-3065 are "expired" and §63-3079
  ("Franchise tax not repealed") is "repealed". All three are in force; the
  adapter's `_section_status` matches those words anywhere in the body. The
  rows carry the same status in the 2026-09-14 scope, and this PR keeps plain
  rows identical, so the fix is a separate change (follow-up 1).
- **Claim audit** (`out-claim-audit.md`) did not run. Its brief forbade
  commands, so the Codex lane that took it could not read files. It was rerun
  in round 2.

### Round 2 (2026-10-12, on this branch)

REVIEW_ROUND_2_PLACEHOLDER

## Follow-ups (not in this PR)

1. **Idaho status heuristic.** `_section_status` should mark only a section's
   own status. Filed as a separate task; it affects §§63-3049, 63-3065 and
   63-3079 in this chapter.
2. **Schema text.** When #752 merges, add an Idaho row to the variants table in
   `schema/citation-path.v1.md` §4.0: `us-id/statute/63-3022E--effective-2027-01-01`.
3. **Ratchet merge order.** This PR raises `uppercase_segments` from 18,796 to
   18,798: the two variant paths keep Idaho's capital section suffixes (E, D).
   Any other open PR that raises the same baseline must re-measure it after the
   first of them merges.
4. **rulespec-us.** At the TY2027 encoding of §§63-3022E and 63-3025D:
   - cite the `--effective-2027-01-01` rows, or the plain rows of a scope
     extracted on or after 2027-01-01;
   - consider renaming the two `…_66_402_5` inputs.
5. **§66-402.** Idaho Code Title 66 is not in the corpus. The
   developmental-disability definition is an input in rulespec-us today.

## Checks

CHECKS_PLACEHOLDER

## Certification

The ingest manifest attests this note as its reasoning log by SHA-256. It is
signed after the last edit to this note, from the clean content commit, with the
ingest key read from the agent secret store into the environment. Signing also
writes the scope's lock file and uploads its new objects:

```bash
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus \
  --jurisdiction us-id --document-class statute \
  --version 2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30 \
  --command "uv run axiom-corpus-ingest extract-state-statutes --base data/corpus --manifest manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml" \
  --reasoning-log docs/ingest-runs/2026-09-27-id-title-63-chapter-30-concurrent-versions.md \
  --lock --push
```
