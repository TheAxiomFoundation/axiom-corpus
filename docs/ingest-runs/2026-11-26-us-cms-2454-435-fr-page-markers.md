# 42 CFR 435.550-435.563 without Federal Register page breaks

Date: 2026-11-26.
Branch: `fix/cms-435-fr-page-markers`, cut from `origin/main` at `075c5cdd8` (#996 merged).
Purpose: ruling d2932, "fix the corpus rows (xx one-line amendatory body, FR page markers)", for
the CMS-2454 community engagement sections that rulespec-us#2238 re-encodes under
`--require-complete-source-unit`.

`us/regulation/2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-corrected-r2026-07-24-self-contained`
holds 42 CFR 435.550-435.563 as Federal Register raw text slices
(`federal-register-raw-text-slice`). Twelve rows come from 2026-11094 (91 FR 33348), and
435.557 and 435.558 come from the correction C1-2026-11094 (91 FR 39028). This run builds the
successor
`us/regulation/2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-corrected-r2026-07-24-self-contained-r2026-11-26-fr-page-markers`.
It keeps the same 14 rows and changes only their bodies.

This branch publishes, loads, activates, signs and locks nothing, and it adds or edits no
tracked selector. The main session does the signing and the selector cut after review (see
"Signing (TODO)").

## Problem

The slicer (`_federal_register_cfr_section_body`) stores the GPO raw text as printed. Two
features of that text mislead readers that take a line-initial label for a paragraph start:

- **Page breaks.** Each page break prints as a `[[Page N]]` line between blank lines. The base
  rows hold nine of them in eight rows: 552, 554, 555, 556, 557 (two), 558, 561 and 563. Six
  of the nine fall inside a sentence. In 435.558(b)(1), for example, the text reads "after
  reviewing the information provided by", then `[[Page 39031]]`, then "the individual at
  application".
- **Hard wraps.** Paragraphs wrap at about 72 columns, with every continuation line at
  column 0. Nine continuation lines begin with `(`:
  - 552: `(d)(1)(i) of this section by 4.33 weeks`, `(4) of this section for a total`;
  - 554: `(c)(1)(i)(A) through (C) of this section.`;
  - 556: `(b) of this subchapter`;
  - 558: `(c)(1)(i) or (ii) of this section`, `(PTC) used`, `(a)(2) of this section ends`;
  - 561: `(a) of this section must be provided`, `(PTC) used`.

  axiom-encode's `recognize_source_structure` opens phantom paragraphs at those lines, as
  "Downstream" shows.

The task brief counted "10 markers in 9 rows". A recount on the locked rows gives 9 markers in
8 rows, and the brief's own list of rows sums to 9 in 8. The d2932 critic's recount agrees.

## The rule, checked on all 14 bodies first

Before any code was written, a read-only pass over the 14 locked bodies tested the layout. It
covered indent counts, trailing spaces, blank lines and the line after each marker, and it
compared each body line for line against the eCFR section's paragraphs. Findings:

- **Indents.** Non-blank lines are indented 0 or 4 spaces. No line has another indent, no line
  holds a tab, and no section has a table. The eCFR XML of these sections holds only `HEAD`,
  `P`, `CITA` and inline `I`/`E`.
- **Paragraph starts.** None sits at column 0. Once the markers are dropped and the column-0
  lines joined, every row gives exactly one line per eCFR heading or paragraph.
- **Ordinary wraps** keep the space they wrapped at on the line before. 836 lines end in one
  space and 28 in two. All 28 two-space lines end in `Sec.`, and the next line starts with the
  section number. Deleting only the line break keeps `Sec.  435.554` as printed. Stripping the
  spaces and joining with one space would turn it into `Sec. 435.554`.
- **Hyphenated wraps** are the exceptions. Four lines end in the hyphen of a compound word, with
  no trailing space: 555 `short-`/`term`, 557 `short-`/`term` and `unemployment-`/`based`, and
  558 `short-`/`term`. eCFR prints `short-term` and `unemployment-based`, so these join with
  nothing between the parts.
- **Page-break junctions.** The line before a marker never keeps a trailing space ("hours
  spent" / "attending", "provided by" / "the individual"). So each of the six mid-sentence
  markers (552, 556, 557 twice, 558, 561) becomes one space. A marker before an indented
  paragraph start (554 after "following:", 555 after "provide:") becomes a line break. 563's
  marker is the last line of its body, so nothing replaces it.
- **Headings.** Five headings wrap onto a column-0 second line (556, 557, 559, 562, 563).
  Joining that line gives eCFR's one-line `HEAD`. Blank lines occur only after the heading and
  around markers.

## Code change

`src/axiom_corpus/corpus/federal_register.py` adds `normalize_federal_register_cfr_section_body`,
a pure function whose docstring states the rule:

1. Remove each `[[Page N]]` line with its blank lines.
2. Join each column-0 line onto the line before it by dropping the line break. Only where a page
   marker stood and the line before ends in a word does one space take the break's place.

The result is the heading on one line, a blank line, then one line per paragraph, each with its
four-space indent. Only line breaks are removed or turned into spaces. The function refuses any
body outside the rule with a `ValueError`:

- a marker that is not alone on its line between blank lines;
- a tab, a non-LF line separator, or an indent other than 0 or 4 spaces;
- a blank line anywhere but after the heading, or an indented heading line;
- a first paragraph at column 0, such as an amendatory `* * * * *` slice;
- an ordinary wrap whose line ends in neither a space nor a hyphen;
- a page break between a line ending in a dash (`--`) and a column-0 continuation. The raw
  text drops the space before a page break, so whether a space followed the dash cannot be
  known. None of the 14 rows has that junction.

The extractor itself is unchanged: `extract_federal_register_cfr_sections` still writes verbatim
slices, so every existing scope reproduces as before. Wiring the normaliser into the extractor
would change what that command writes. That is a separate decision (see "Open questions").

## Successor scope

`scripts/repro/us_cms_2454_435_fr_page_markers.py` builds the successor in two steps:

```bash
uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py fetch --base data/corpus   # once, network
uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py build --base data/corpus   # offline
```

**Input: the base scope's locked rows.** The base scope keeps 2026-11094 as the
federalregister.gov HTML page (1,277,858 bytes), not as raw text. So 12 of the 14 rows have no
retained raw text to re-slice. The build follows `scripts/compose_scope_versions.py`, the
precedent for a scope derived from scopes, and works as follows:

- It refuses a base unless the inventory and provisions files carry their locked sha256
  (`93c35a63…`, `ef36b032…`).
- It copies the three retained sources byte for byte, each checked against its locked sha256:
  - `federal-register/documents/C1-2026-11094.txt`;
  - the 2026-11094 HTML under `official-documents/`;
  - that HTML's provenance record.
- For 435.557 and 435.558 it also re-slices the retained C1-2026-11094 raw text with
  `_federal_register_cfr_section_body`. It requires each slice to equal the base body byte for
  byte, and both do.

**Verification sources.** The successor also keeps 14 eCFR section XML files with provenance
records, in the shape of the MT successor's verification sources:
`ecfr/title-42-section-435.5NN.xml` and `provenance/ecfr-title-42-section-435.5NN.json`.

- `fetch` ran at 2026-11-26T11:49Z (`date -u`). It requested
  `https://www.ecfr.gov/api/versioner/v1/full/2026-07-31/title-42.xml?part=435&section=435.5NN`
  with gzip.
- Each request returned HTTP 200. 2026-07-31 is the rows' expression date and the date of each
  section's one eCFR version.
- The decoded bytes of all 14 files are identical (sha256) to the copies the d2932 scoping run
  fetched at date 2026-11-24 at about 10:32Z.

The XML files serve only as checks: no field of any row comes from them.

**Rows.** Each row keeps every field of its base row except these five:

| Field | Successor |
| --- | --- |
| `body` | normalised |
| `version` | the successor version |
| `id` | `deterministic_provision_id(path, version)`, the base's own scheme |
| `source_path` | the same leaf under the successor's sources |
| `metadata` | the base metadata plus `successor_of_version`, `successor_of_source_path` (the base row's source path) and `verification_source_paths` (that section's eCFR XML) |

Inventory items keep their sha256, source URL and source format, and get the same source-path
rewrite and the three lineage keys. `source_format` stays `federal-register-raw-text-slice`.
The `heading` field is unchanged, including the double space that a wrapped heading left in
556, 559, 562 and 563 ("engagement  requirement").

The successor scope holds 14 rows, and coverage is complete at 14 of 14. Its files are:

- `inventory/…json`: sha256 `9b8e8a01…`, 28,076 bytes;
- `provisions/…jsonl`: `ce06ea84…`, 106,370 bytes;
- `coverage/…json`: `2cb5ff45…`, 422 bytes;
- 31 source files: the 3 retained sources, plus 14 eCFR XML files and their 14 provenance
  records.

| Section | Source | Base chars / lines | Successor chars / lines | Page markers | Column-0 `(` lines |
| --- | --- | ---: | ---: | ---: | ---: |
| 435.550 | 2026-11094 | 214 / 5 | 212 / 3 | 0 | 0 |
| 435.551 | 2026-11094 | 760 / 15 | 754 / 9 | 0 | 0 |
| 435.552 | 2026-11094 | 9,582 / 162 | 9,456 / 49 | 1 | 2 |
| 435.553 | 2026-11094 | 796 / 14 | 791 / 9 | 0 | 0 |
| 435.554 | 2026-11094 | 8,771 / 148 | 8,649 / 40 | 1 | 1 |
| 435.555 | 2026-11094 | 8,176 / 139 | 8,066 / 43 | 1 | 0 |
| 435.556 | 2026-11094 | 3,448 / 61 | 3,387 / 13 | 1 | 1 |
| 435.559 | 2026-11094 | 960 / 17 | 948 / 5 | 0 | 0 |
| 435.560 | 2026-11094 | 3,311 / 58 | 3,273 / 20 | 0 | 0 |
| 435.561 | 2026-11094 | 5,744 / 103 | 5,672 / 44 | 1 | 2 |
| 435.562 | 2026-11094 | 2,452 / 45 | 2,424 / 17 | 0 | 0 |
| 435.563 | 2026-11094 | 495 / 12 | 473 / 4 | 1 | 0 |
| 435.557 | C1-2026-11094 | 19,838 / 317 | 19,549 / 54 | 2 | 0 |
| 435.558 | C1-2026-11094 | 9,250 / 156 | 9,123 / 42 | 1 | 3 |

The successor bodies have no `[[Page` and no line that starts at column 0 with `(`.

## Text identity with eCFR

The build checks every body against its section's eCFR XML. For the comparison, it folds
section signs to `Sec.` and `Sec. Sec.`, em dashes to `--`, GPO opening backtick pairs to
`“`, and GPO closing apostrophe pairs to `”`. It also collapses whitespace. It compares the
heading (`HEAD`) and paragraphs (`P`) and skips the citation note (`CITA`). The body's
nonblank lines match one for one in all 14 sections.

| Section | Compared chars | Lines = eCFR heading + paragraphs |
| --- | ---: | ---: |
| 435.550 | 205 | 2 |
| 435.551 | 719 | 8 |
| 435.552 | 9,258 | 48 |
| 435.553 | 758 | 8 |
| 435.554 | 8,486 | 39 |
| 435.555 | 7,882 | 42 |
| 435.556 | 3,321 | 12 |
| 435.557 | 19,292 | 53 |
| 435.558 | 8,917 | 41 |
| 435.559 | 927 | 4 |
| 435.560 | 3,191 | 19 |
| 435.561 | 5,471 | 43 |
| 435.562 | 2,353 | 16 |
| 435.563 | 462 | 3 |

The same check fails on all 14 base bodies, because their lines are hard-wrapped. So it does
not pass vacuously.

The folds have known limits, and none applies to these 14 sections:

- **Literal punctuation.** A literal `''` or `--` in eCFR would match a GPO closing quote or
  em dash. The 14 eCFR sections contain no `''`, `--` or backtick, and every `''` in the 14
  bodies follows its own ``` `` ```.
- **Section signs.** `§ §` and `§§` fold to the same text. eCFR has no `§ §` here, and each
  body's count of `Sec. Sec.` equals its section's count of `§§`: 1 in 435.556, 8 in 435.557,
  4 in 435.558, 2 in 435.559, 5 in 435.560, 1 in 435.561 and 5 in 435.562.
- **Typography-only refusals.** A future section can fail for typography alone, such as the
  Federal Register's `[deg]` where eCFR prints `°`, or straight against curly apostrophes.
  The build then raises rather than guessing.

## Invariants

`tests/test_us_cms_2454_435_fr_page_markers.py` (29 tests) checks the following:

- **Conservation.** In every row, the successor keeps the base's non-space characters less the
  markers.
  - With line breaks deleted from both texts, they differ only by single inserted spaces: one
    per mid-sentence marker, six in all.
  - The word sequence is the base's less the 18 whitespace tokens of the nine markers (each
    `[[Page N]]` splits into two), with exactly the four hyphen wraps rejoined.
  - So a plain `split()` comparison is not conserved at those four places, by design: base
    `short-` + `term` becomes `short-term`.
- **No marker left.** The test also pins the base's markers per row.
- **Lines.** In every successor body:
  - line 1 is the `Sec.  435.5NN` heading and line 2 is blank;
  - every other line is a four-space-indented paragraph with no trailing whitespace;
  - none of the base's nine column-0 cross-reference lines begins a line.
- **eCFR identity**, as above, plus a negative case in which one changed word in the 435.558
  XML fails the check.
- **Reproducibility.**
  - Two builds into temporary bases are byte-identical.
  - Both are byte-identical to the scope in `data/corpus`: inventory, provisions, coverage and
    all 31 source files.
  - The build refuses a base provisions file whose bytes differ from the lock.
- **Citation set.** The 14 paths are those of the base, in the base's order.
- **Fields.** Only `body`, `version`, `id`, `source_path` and `metadata` differ from the base,
  and `metadata` differs only by the three lineage keys. Inventory hashes and source bytes are
  unchanged.
- **Corrected rows.** The 557 and 558 base bodies are slices of the retained C1-2026-11094 text.
- **Fetching.** `ensure_corpus_inputs` places the locked inputs the build reads: the base
  scope's sources, inventory and provisions, and the successor's eCFR checks. It never places
  the successor's inventory, provisions or coverage. The resolver places a scope's source
  directory whole, so the three copied sources come too.
- **Release validation.** The successor alone validates with 0 issues. Base plus successor is
  rejected with exactly 14 `duplicate_release_citation` errors.

`tests/test_corpus_federal_register.py` tests the normaliser itself:

- a worked example covering a mid-sentence marker, a marker before a paragraph, a trailing
  marker, a hyphen wrap, a `Sec.  ` wrap and a heading wrap;
- idempotence;
- 14 refusal cases;
- a Hypothesis round trip with 400 examples. Each example prints a section as raw text: one- or
  two-space gaps, wraps at gaps and inside hyphenated words, and page breaks inside and between
  paragraphs and at the end. The normaliser must return the one-line-per-paragraph text.

Each of four mutants of the join rule fails that property in 300 examples (a scratch mutation
run):

| Mutant | Failing examples |
| --- | ---: |
| Space after a hyphen at a marker | 102 |
| Strip and join with one space | 190 |
| Never insert a space | 168 |
| Keep the blank line before a marker | 229 |

## Downstream: axiom-encode structure and numeric recall

Measured with axiom-encode `origin/main` `681c323bf` (`python -I`, `sys.path` at its `src`). The
checkout carries an uncommitted USC-outline change to `source_completeness.py`. A rerun against a
`git archive` export of the same commit gave identical results, so that change does not touch
these rows. "eCFR" means the eCFR body laid out as `ecfr.py` lays out sections: paragraphs
whitespace-collapsed and joined by blank lines.

`recognize_source_structure` branches (base / successor / eCFR):

| Section | Base | Successor | eCFR |
| --- | ---: | ---: | ---: |
| 435.550 | 0 | 0 | 0 |
| 435.551 | 6 | 6 | 6 |
| 435.552 | 49 | 45 | 45 |
| 435.553 | 6 | 6 | 6 |
| 435.554 | 34 | 32 | 32 |
| 435.555 | 41 | 41 | 41 |
| 435.556 | 12 | 11 | 11 |
| 435.557 | 52 | 52 | 52 |
| 435.558 | 44 | 40 | 40 |
| 435.559 | 3 | 3 | 3 |
| 435.560 | 18 | 18 | 18 |
| 435.561 | 43 | 42 | 42 |
| 435.562 | 15 | 15 | 15 |
| 435.563 | 2 | 2 | 2 |

The successor's branch paths equal eCFR's in all 14 rows. The scoping critic predicted 45, 32,
11, 40 and 42 for the five affected rows. The successor removes these phantom paths:

- **554:** `c/1/i/a/...` becomes the real `c/3/i/a`-`c` and `c/3/ii`.
- **558:** `c/1/c/...` and root-level `iii`, `iii/a` become `c/1/iv`-`vii`, `c/2`-`4`,
  `d/2/iii/a`-`b` and `d/2/iv`.
- **556:** `b/1`, `b/2` become `d/1`, `d/2`.
- **561:** `a/1/i`-`iv` and `a/3/...` become `c/1/...`, `c/3/...`, `d` and `d/1`.
- **552:** `d/1/d/...` and `e/4/1`-`4` become `d/2` and `e/1`-`3`.

`complete_source_numeric_recall_occurrences`, base to successor:

- The multiset of demanded numbers is unchanged in 13 rows.
- In 435.552 the successor drops one false `1986`. The base wraps "Internal Revenue \nCode of
  1986", and the act-title filter does not match across the line break.

The eCFR-shaped bodies would instead add false section-number demands, the `§§` list defect the
scoping run found:

| Section | Added demands |
| --- | --- |
| 556 | 435.918 |
| 557 | 435.556 ×5, 435.563, 435.949, and five 12s |
| 558 | 435.556, 435.918 ×2 |
| 559 | 435.556, 435.563 |
| 560 | 15 more |
| 561 | 435.562 |
| 562 | five more |

The Federal Register route keeps `Sec. Sec.` and avoids all of them.

## Release lines

No selector is cut here. The pin-line selectors that carry the base, such as
`us-rulespec-2026-11-14-cms-smd-26-006` and `us-rulespec-2026-11-24-tier1-source-text`, swap it
for the successor in the next cut. Never select the two together: they share all 14 paths.

The successor's citation set equals the base's, so a swap cannot change release-wide citation
uniqueness. Parent checks are scope-local, and neither scope has parents.

The 1396a(xx) statute successor (unit xx) belongs in the same cut. Two new selectors that name
the same predecessor form a fork, and `selector_lineage.py` rejects a fork that
`manifests/selector-lineage-baseline.yaml` does not record.

## Checks

Run on this branch over `075c5cdd8`:

- **Tests.** `AXIOM_CORPUS_PARTIAL_TESTS=1 pytest -n 0 tests/test_us_cms_2454_435_fr_page_markers.py
  tests/test_corpus_federal_register.py tests/test_cms_435_correction_release.py`: 50 passed.
  Only the base scope is fetched here, so the whole suite (it needs `corpus fetch --all`) was not
  run.
- **Coverage.** `axiom-corpus-ingest coverage ... --version <successor> --write`: complete, 14 of
  14, and the rewrite left the file unchanged.
- **Content check.** The `content-check` CLI accepts only locked scopes, so it ran the CLI's own
  `release_policy.scan_scope` on the unlocked successor: 0 findings, as for the base.
- **Release validation.** `axiom-corpus-ingest validate-release --strict-warnings` ran on scratch
  selectors (not committed), under `complete-expression-dates-v1` with `AXIOM_CORPUS_NO_FETCH=1`:
  - the successor alone: ok, 0 issues;
  - the base alone: ok, 0 issues;
  - base plus successor: exit 2, with 14 issues, all `duplicate_release_citation`.
- **Citation paths.** `scripts/validate_citation_paths.py` over the two local scopes: ok, with no
  irregular paths and no identity drift.
- **Lint and types.** `ruff check .` passes. `ruff format --check` passes on the four changed
  Python files. `mypy --ignore-missing-imports` finds no issues in `federal_register.py` or the
  script. `towncrier build --draft` renders the fragment under Fixed; `towncrier check` needs a
  commit to compare, so it waits for the commit.

## Open questions

1. **Extractor default.** Should `extract_federal_register_cfr_sections` normalise by default,
   or behind a flag? Doing so changes what existing commands reproduce. `us/regulation/42/438/58`
   in `2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments-r2026-07-15-self-contained` still
   carries `[[Page 33482]]`. It is an amendatory slice, though, and the normaliser refuses those
   (a first paragraph at column 0, `* * * * *`), so it needs its own rule.
2. **Wrapped headings.** The `heading` field keeps the double space from wrapped headings. The
   brief said to keep labels as they are, so this run leaves them.
3. **Version suffix.** `-r2026-11-26-fr-page-markers` follows the `-rYYYY-MM-DD-<slug>`
   convention, but the change also unwraps lines. `line-structure`, the New York precedent's
   slug, would describe it more fully. This run kept the name the brief gave.
4. **Verification sources.** The 14 eCFR files enlarge the signed file set by 28 small files.
   They follow the MT precedent (`verification_source_paths`). Dropping them would turn the
   eCFR identity test into a scratch-only check.

## Signing (TODO)

Not run in this branch. After review, from a clean tracked tree whose HEAD carries this change:

```bash
uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py build --base data/corpus
AXIOM_CORPUS_INGEST_PRIVATE_KEY="$(agent-secret get agent/axiom-corpus-ingest-private-key)" \
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus \
  --jurisdiction us --document-class regulation \
  --version 2026-06-29-cms-2454-ifc-42-cfr-435-community-engagement-corrected-r2026-07-24-self-contained-r2026-11-26-fr-page-markers \
  --command 'uv run --extra dev python scripts/repro/us_cms_2454_435_fr_page_markers.py build --base data/corpus (verification sources: ... fetch --base data/corpus, 2026-11-26T11:49Z; run note: docs/ingest-runs/2026-11-26-us-cms-2454-435-fr-page-markers.md)' \
  --lock --push
```

Then:

- Commit `.axiom/ingest-manifests/us/regulation/<successor>.json` and
  `.axiom/corpus-locks/us/regulation/<successor>.json` together.
- Run `axiom-corpus-ingest content-check us/regulation/<successor> --check-baseline`. If the
  baseline needs the scope's entry, record it with `--update-baseline` and commit
  `manifests/release-content-baseline.json`.
- Run `axiom-corpus-ingest guard-ingested --base-ref origin/main`.
- Run `axiom-corpus-ingest corpus verify --remote --attest --changed-since origin/main`.

R2 already holds the three retained sources, since their bytes are the base scope's. `--push`
uploads only the new inventory, provisions, coverage and eCFR objects.
