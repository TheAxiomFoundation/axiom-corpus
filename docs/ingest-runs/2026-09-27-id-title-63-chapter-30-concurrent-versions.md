# Idaho Title 63 chapter 30: the 2027 text of §§63-3022E and 63-3025D as variant rows (2026-09-27)

Follow-up 4 of the recovery sibling-scope audit (#757,
`docs/ingest-runs/2026-09-27-recovery-sibling-scopes-audit.md`, "Idaho"). The
official pages for Idaho Code §§63-3022E and 63-3025D print two versions of
each section, "[effective until January 1, 2027]" and "[effective January 1,
2027]". Both Idaho carriers hold only the first:

- `us-id/statute/2026-07-31-id-title-63-chapter-30-successor`, carried by ten
  selectors: `us-rulespec-2026-07-31-idaho-statutes-current` through
  `us-rulespec-2026-09-13-cms-state-plans-union`, and
  `us-rulespec-2026-09-24-snap-fy2027-cola`;
- `us-id/statute/2026-09-14-income-tax-chapter-us-id-title-63-chapter-30`,
  carried by `us-rulespec-2026-09-14-wave4-union` and
  `us-rulespec-2026-09-14-wave4-r2-union`.

| scope | rows | coverage |
|---|---:|---|
| `us-id/statute/2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30` | 166 | complete, 166 / 166, 0 missing, 0 extra |

The scope is the 2026-09-14 chapter scope, re-extracted offline from the 165
pages it retained, plus two variant rows:

- `us-id/statute/63-3022E--effective-2027-01-01`
- `us-id/statute/63-3025D--effective-2027-01-01`

It is not published to R2, loaded into Supabase or added to a release selector.
It carries a signed ingest manifest.

## The whole chapter

All 162 section pages the chapter scope retained were read, three ways:

1. **Rendition split.** The adapter's splitter (`_section_renditions`) counts the
   divs that open with the section number and a heading. Exactly two pages
   print more than one: §63-3022E and §63-3025D, two renditions each. The other
   160 print one. A test pins this
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

**Live check.** On 2026-09-27 the adapter re-extracted the chapter from
legislature.idaho.gov (network, `expression_date` 2026-09-27) into a scratch
base. It gave the same 166 citation paths, in the same order. Every row had the
same heading, body, label, ordinal, parent and metadata as this scope,
including both variant rows. The raw bytes of all 165 pages differ from the
2026-09-14 retrieval. In `63-3022E.html` the six changed lines are WordPress
nonces in inline scripts. No difference reaches an extracted row.

## What the two versions say

2026 Idaho Sess. Laws ch. 79 amends both sections (sec. 29 for §63-3022E,
sec. 30 for §63-3025D), effective January 1, 2027. The two versions of each
section are word-for-word identical except for the marker and one cross-reference,
which occurs twice, in (1) and (4):

| in force until 2027-01-01 | effective 2027-01-01 |
|---|---|
| "as defined in subsection (5) of section 66-402 , Idaho Code" | "as defined in section 66-402 (4), Idaho Code" |

A test checks this: after that substitution, and the marker's, the bodies are
equal (`test_the_two_versions_differ_only_in_the_marker_and_the_66_402_reference`).

The same act amends §66-402 (sec. 32). The live §66-402 page on 2026-09-27
prints two renditions too. In the 2027 text the definitions of "Artificial
life-sustaining procedures" and "Manage financial resources" are gone, so
"Developmental disability" moves from (5) to (4). Its four lines of text are
identical in both renditions apart from that number. §66-402 is not in the
corpus.

## Convention

Neither convention the brief names has landed: #752 (CA LegInfo concurrent
versions) and #754 (ME "TEXT EFFECTIVE UNTIL / TEXT EFFECTIVE") were both open
on 2026-09-27. The convention on `origin/main` (f1916d73b) is New Mexico's,
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
plain row stays byte-identical in content to the row both carriers hold.

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
| `metadata.status` | absent (as before) | `future_or_conditional`; an expired "until" variant would be `effective_until`. The vocabulary is NM's, DE's, NV's and RI's. |

The variant row sits right after its plain row in the provisions and inventory
files.

**Naming rules for a non-primary rendition.**
- "[effective <date>]" gives `effective-<ISO date>`.
- "[effective until <date>]" gives `effective-until-<ISO date>`.
- A rendition with no marker gives `variant-<n>`, where n is its 1-based printed
  position (NM's fallback).
- Two renditions with the same name fail closed.

## Adapter change (`src/axiom_corpus/corpus/state_adapters/idaho.py`)

- **`parse_idaho_section_versions`** (new) returns every rendition. The one in
  force comes first, at the plain path; the others follow in printed order as
  variants.
- **`parse_idaho_section_page`** keeps its signature and meaning: it returns the
  first of those. The 2026-07-31 repro script and its test use it unchanged.
- **`_select_section_rendition`** is replaced by three helpers:
  - `_section_renditions`: the spans. A rendition starts at each div that
    opens with the section number and a heading. It ends at the next such div,
    or at the History marker after the last one.
  - `_primary_rendition`: the old selection rule.
  - `_rendition_divs`: the shared page prefix, one rendition, then the shared
    History and notes.

  The span arithmetic and the selection rule are unchanged:
  - exactly one marked rendition in force wins;
  - otherwise a lone unmarked rendition wins;
  - otherwise the parse raises "no unique rendition".

  A property test checks this against a verbatim copy of the old function,
  error for error.
- **Pages with one rendition** are still read whole, and their markers are still
  never parsed. So a malformed date on such a page cannot newly fail.
- **The extractor** emits each page's sections in order. The `limit` option
  still counts section listings, not rows.
- **Metadata.** `_section_record` and `_section_inventory_item` add `variant`,
  `canonical_citation_path` and `effective_note` to variant rows only.
- **Default.** Variant rows are emitted by default, with no option, as the NM,
  DE, NJ, NV and RI adapters do. A page with one rendition extracts exactly as
  before.

Callers were found by text search: `cli.py` (`extract_idaho_statutes`),
`scripts/repro/idaho_title_63_chapter_30_successor.py` and the tests.
GitNexus could not help:
- `impact` fails on this checkout's index (storage version 42; the CLI reads 40,
  as #754 found).
- `detect_changes` reads the main clone, not this worktree, and reports nothing.

## Extraction

Manifest `manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml`:

- **Source.** `source_dir` is the 2026-09-14 chapter scope's retained sources:
  the title index, the Title 63 page, the chapter 30 page and 162 section pages.
  The adapter reads them and never falls back to the network.
- **Dates.** `source_as_of` and `expression_date` stay 2026-09-14.
- **Filters.** `only_title` 63 and `only_chapter` 30.
- **Scope name.** The adapter appends `-us-id-title-63-chapter-30` to the version.

```bash
uv run axiom-corpus-ingest extract-state-statutes --base data/corpus \
  --manifest manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml
```

Result: 166 provisions, 1 title, 2 containers, 164 section rows (162 sections
and 2 variants), 165 source files, 0 errors, coverage complete. The 165 source
files are byte-identical to the 2026-09-14 scope's, and git stores them as the
same blobs. `.gitattributes` marks the scope's HTML `binary`, like the other
recent scopes: every retained Idaho page has CRLF line endings.

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

In `tests/test_corpus_idaho.py`, over 400 Hypothesis-generated pages of one to
four renditions per run. Each rendition has no marker, "[effective <date>]" or
"[effective until <date>]", checked at any expression date from 2024 to 2029.
The generated cases cover:
- 0 to 3 variants;
- both fail-closed cases: no unique rendition in force (about 37% of cases) and
  two variants with one name (about 4%).

1. **Selection.** The plain section is the one rendition in force under the
   model, or parsing raises. A page with one rendition is read whole.
2. **Differential.** The plain section equals what the pre-change adapter
   produced (a verbatim copy of `origin/main` f1916d73b's
   `_select_section_rendition`), including identical error messages. No plain
   row can move.
3. **Conservation.** Each printed rendition is exactly one section, with its own
   heading and body. Variants follow in printed order after the plain section.
   Every section has the page's History.
4. **Naming.** Variant names follow the markers and are unique or rejected. They
   give sibling paths that match the citation-path grammar, whose
   `canonical_citation_path` is the plain path.
5. **Status.** A dated variant is never in force on the expression date. Its
   `status` and `effective_note` follow its marker.
6. **Determinism.** Parsing twice gives equal results.

In `tests/test_us_id_title_63_chapter_30_concurrent_versions.py`, on the
committed bytes:

7. **Replay.** The manifest's parameters, run with `requests.get` patched to fail,
   rebuild the provisions, inventory and coverage byte for byte. All 165
   sources equal the committed ones and the 2026-09-14 retained ones.
8. **Differential against the chapter carrier.** Every one of its 164 rows is
   present, in the same order, equal in every field except `version` and
   `source_path`. The only additions are the two variants, each right after its
   plain row.
9. **Differential against the 2026-07-31 carrier.** Its seven rows are present,
   with the same heading, body, label, identifiers, kind, level and parent. Each
   section row also has the same metadata. What differs:
   - ordinals: that scope numbered its five sections 1 to 5;
   - the chapter row's `chapter_pdf_url`;
   - `expression_date`: 2026-07-13 there.
10. **Variant rows.** Each variant row shares every placement and source field
    with its plain row, has its own id, and begins with the 2027 marker.
11. **Versions differ only in the reference.** The two versions of each section
    differ only as described under "What the two versions say".
12. **Completeness.** Only §§63-3022E and 63-3025D of the 162 retained pages print
    more than one rendition, two each.
13. **No stray variants.** No other us-id scope carries a `--` path.
14. **Release.** In place of each newest line's us-id statute scope (the
    2026-07-31 successor in `us-rulespec-2026-09-24-snap-fy2027-cola`, the
    chapter scope in `us-rulespec-2026-09-14-wave4-r2-union`), the scope
    validates with strict warnings and 0 issues. It keeps every citation path
    the replaced scope carried.

## rulespec-us

rulespec-us `origin/main` 54d90a725 encodes both sections:
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

This PR adds no selector. The cut, queued for Max, would put this scope in place
of the us-id statute scope in a successor of each line head.

Selectors descend from `us-rulespec-2026-08-08-obbb-alien-snap` in two
branches, each named in the successor's `description`. Two selectors are heads
today: no other selector names them as its predecessor.

- **wave4 branch.** The chain is obbb → `…-08-09-cutover-surface-union` →
  `…-08-23-canada-338-suspension-union` → `…-09-11-program-ingestion-union` →
  `…-09-13-followup-union` → `…-09-13-federal-and-plans-union` →
  `…-09-13-cms-state-plans-union` → `…-09-14-wave4-union` →
  `us-rulespec-2026-09-14-wave4-r2-union`.
  - The head carries `2026-09-14-income-tax-chapter-us-id-title-63-chapter-30`;
    replace it.
  - The effect is the two variant rows. Every other row is the same.
- **snap-fy2027 branch.** The chain is obbb → `us-rulespec-2026-09-24-snap-fy2027-cola`.
  - The head carries `2026-07-31-id-title-63-chapter-30-successor`; replace it.
  - All seven of its paths keep their text. This includes every Idaho path
    rulespec-us cites (§§63-3022D, 63-3022E, 63-3024, 63-3024A, 63-3025D).
  - The swap adds the other 157 chapter 30 sections and the two variants.
  - Rows move from `expression_date` 2026-07-13 to 2026-09-14.

Each head holds one us-id statute scope, so the swap is one scope per head. The
release test validates both swaps. This PR edits no existing selector.

## Review

(To be completed after the independent review.)

## Follow-ups (not in this PR)

1. **Schema text.** When #752 merges, add an Idaho row to the variants table in
   `schema/citation-path.v1.md` §4.0: `us-id/statute/63-3022E--effective-2027-01-01`.
2. **Ratchet merge order.** This PR raises `uppercase_segments` from 16,280 to
   16,282: the two variant paths keep Idaho's capital section suffixes (E, D).
   #754 raises the same baseline to 20,490. Whichever merges second needs the
   sum, 20,492, measured on the merged tree.
3. **rulespec-us.** At the TY2027 encoding of §§63-3022E and 63-3025D:
   - cite the `--effective-2027-01-01` rows;
   - consider renaming the two `…_66_402_5` inputs.
4. **§66-402.** Idaho Code Title 66 is not in the corpus. The
   developmental-disability definition is an input in rulespec-us today.

## Checks

(Completed below before signing.)

## Certification

The ingest manifest attests this note as its reasoning log by SHA-256. It is
signed after the last edit to this note, from the clean content commit, with the
ingest key read from the agent secret store into the environment:

```bash
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus \
  --jurisdiction us-id --document-class statute \
  --version 2026-09-27-income-tax-concurrent-versions-us-id-title-63-chapter-30 \
  --command "uv run axiom-corpus-ingest extract-state-statutes --base data/corpus --manifest manifests/us-id-statutes-title-63-chapter-30-concurrent-versions.yaml" \
  --reasoning-log docs/ingest-runs/2026-09-27-id-title-63-chapter-30-concurrent-versions.md
```
