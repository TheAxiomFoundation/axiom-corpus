# 42 U.S.C. 1396a(xx) as quoted in Pub. L. 119-21, one element per line

Date: 2026-11-26
Branch `fix/pl-119-21-xx-line-structure`, cut from `origin/main` (075c5cdd8, after #996).

`us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained`
holds 42 U.S.C. 1396a(xx), the community engagement requirement that Pub. L. 119-21
§ 71119(a) adds to the Social Security Act, and its paragraphs (1) to (11): 12 rows. Every
body is one line. This run builds its successor,
`us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained-r2026-11-26-line-structure`,
from the same retained USLM bytes, with one structural element per line and without the
Statutes at Large page markers, margin notes and amendatory quotes. It keeps the 12 citation
paths.

Nothing is signed, locked, pushed, published or activated, and no tracked selector is added
or edited (see "Signing (TODO)" and "Release lines").

## Problem

The released rows come from `scripts/extract_pl119_21_medicaid_community_engagement.py`
(#150), carried unchanged into the `-r2026-07-15-self-contained` successor. Its
`_normalized_text` joins every `itertext()` part of the USLM `quotedContent` with a space and
collapses whitespace, so each body is one line holding:

- the eight Statutes at Large page markers `139 STAT. 307` to `139 STAT. 314`, mid-sentence
  where a printed page ends (`… subject to the succeeding provisions of this subsection, 139
  STAT. 307 a State shall provide …`);
- the eleven `<sidenote>` margin notes (16 printed lines, such as `Deadline.` before the (1)
  heading and `Determination. Criteria. Regulations.` inside "paragraph (3)");
- the amendatory open quote that USLM keeps inside each quoted `<num>` (`“(1)`), 111 of them
  in the root body, and the closing quote that ends the quotation;
- the row's own number and heading (`“(xx) Community Engagement Requirement for Applicable
  Individuals.—`, `“(1) Deadline. In general.—`).

The root body is 19,151 characters with no line break. axiom-encode's
`recognize_source_structure` finds no outline in it (0 branches, with `origin/main` and with
the fix under "Encoder outline"), so the rulespec-us module for `us/statute/42/1396a/xx`
cannot be checked against its source unit.

## What changes

| | `…-r2026-07-15-self-contained` | `…-r2026-11-26-line-structure` |
| --- | --- | --- |
| Rows | 12: `us/statute/42/1396a/xx`, `…/xx/1` … `…/xx/11` | the same 12, same order |
| Root body | 19,151 characters, 1 line | 18,643 characters, 111 lines: `(1) In general.— Except as provided …`, `(A) in the case of …`, … |
| Paragraph bodies | one line each, starting `“(k) <heading>` | the paragraph's chapeau or content, then one line per descendant; equal to its block of the root body without the `(k) <heading>` prefix |
| Page markers, margin notes | in the text | dropped from the text; kept in `metadata.statutes_at_large` and `metadata.margin_notes` |
| Quotes | `“` before every quoted number; `”` at the end; `‘ applicable individual ’` | no amendatory quotes; inner quotes as printed (`‘applicable individual’`) |
| Lineage | none | `successor_of_version`, `successor_of_source_path`, `verification_source_paths` |
| Source | `uslm/PLAW-119publ21.xml`, sha256 `762ae9af…6dea` | the same bytes, copied |

Every other field is the released row's: `id`, `parent_id`, `parent_citation_path` (the root
stays parentless), `heading`, `kind`, `level`, `ordinal`, `identifiers`, `citation_label`,
`legal_identifier`, `source_url`, `source_format`, `source_id`, `expression_date` 2025-07-04
and `source_as_of` 2025-08-14. The released metadata keys stay, with the same values, and the
inventory metadata equals the row metadata, as in the released scope.

## Source

`sources/us/statute/<version>/uslm/PLAW-119publ21.xml` is copied byte for byte from the
released scope after its SHA-256 is checked against the released inventory:
`762ae9af06640f023ddb9eb6f474ff7cfa275691de338d4fd985cfb04a7b6dea`, 2,787,974 bytes, git blob
`b1c54570db39b3d8d440c0954490018a115f4a9d` (both Pub. L. 119-21 lock files name it). No
publisher traffic.

## How the text is read

`axiom_corpus.corpus.uslm_quoted_content.render_structural_element` renders one USLM
structural element (subsection, paragraph, subparagraph, clause, subclause, item, subitem):

- The row's own `<num>` and `<heading>` are not in its body (the `extract-usc` convention,
  `_BODY_SKIP_TAGS`). The renderer checks for duplicates, children inside the number, and
  unsupported markup inside the heading before omitting them. Its chapeau or content is the
  first line.
- Each descendant structural element starts its own line: its number, its heading if any,
  and its chapeau or content, joined with one space. A `<continuation>` raises
  `UslmRenderError`. This quotation has none.
- `<page>` and `<sidenote>` become metadata. In text blocks and headings, each marker's tail
  stays in the text and its offset points to the next printed character. Markers in the
  row's own heading have body offset zero. The only unspaced join allowed across a marker is
  `.` followed by `—` across a `<sidenote>` within a heading, as in `reason.—` in
  § 70304(a)(3)(B)(ii). A page marker at the same boundary raises even if a sidenote is
  beside it. Each note records the text within its `<p>` children. A nonblank `<p>` tail is
  outside the paragraph and raises.
- A leading `“` is stripped from each rendered `<num>`. The closing `”` is stripped from the
  selected last text node of `quotedContent`, which can be text in a number or heading. In
  this quotation it ends (11)(D)(ii). The `.` after the quotation is outside it. The body
  retains the other quotes as printed, including 6 `‘` and 15 `’`.
- Text nodes are concatenated as the source has them and whitespace collapses to one space.
  The released builder's space-join had put spaces inside the six quoted terms
  (`‘ applicable individual ’`); the successor prints them as the source does.
- `drop_space_before_punctuation` removes a space before `,`, `.`, `;` or `:`, as the released
  builder did. The source has one: `Internal Revenue Code of 1986 .` at the end of (2)(G).

`UslmRenderError` covers unsupported structural and inline elements, nonblank text outside a
text block, ambiguous marker boundaries, nested markers, margin note text outside `<p>`, a
page identifier outside the `/us/stat/<volume>/<page>` format, and a missing selected closing
quote.

One element is printed run-in: subclause (6)(A)(ii)(I) (`class="inline"`, its number `(I)`
without a quote) follows `“(ii)` on the printed line. Following the one-element-per-line rule,
the successor gives `(ii)` a line of its own and starts `(I) provide such individual …` on the
next. See "Open questions".

## Metadata for pages and margin notes

The corpus has no convention for Statutes at Large pages or margin notes (`documents.py` uses
`page_start`/`page_end` for PDF pages of a document). Row metadata is a free mapping, so this
run proposes two nested keys:

- `statutes_at_large`: `volume` 139, `page_start` (the page in effect where the element
  starts: the last `<page>` before it in the document), `page_end` (its last page marker, or
  `page_start`), and `page_breaks`: `[{page, identifier, offset}]`, one per marker inside the
  element, `offset` being where the new page's text starts in the row's body. The root runs
  139 Stat. 306 to 314.
- `margin_notes`: `[{notes, label_path, offset}]`, one per `<sidenote>`: its printed lines,
  the label path of the element it sits in from `xx` (`xx/3/B/i`), and the body offset of the
  next printed character. The root has all 11; each paragraph row has its own.

## Checks the build makes

`scripts/repro/us_pl_119_21_1396a_xx_line_structure.py build` writes nothing unless:

- the released inventory and provisions list the 12 paths, all from the one USLM file whose
  SHA-256 is `762ae9af…`;
- each row's own number is `“(<label>)` and its heading is the released heading (the released
  root heading leaves out the `.—` that its paragraph headings keep);
- each body preserves the released word tokens in order, with the row's own number and
  heading, page markers, margin notes, descendant open quotes and closing quote removed
  at their XML positions. The comparison accounts for the spacing inside single quotation
  marks and rejects changes such as `shall provide` becoming `shallprovide`.
- the closing quote ends the root and (11) and no other row;
- the quoted subsection's 111 label paths, in document order, equal those of codified
  42 U.S.C. 1396a(xx) in the OLRC title 42 XML of release point 119-103
  (`sources/us/statute/2026-10-06-w6-federal-usc-closure-title-42/olrc/xml_usc42@119-103.zip`,
  sha256 `28eaf347…7388`, locked in that scope, which the pin line selects). The codified text
  differs editorially (`section 1315 of this title` for `section 1115`, `this subchapter` for
  `this title`, bracketed notes), so only the structure is compared. The path is recorded in
  `verification_source_paths`; the bytes are not copied into this scope.

```bash
uv run --extra dev python scripts/repro/us_pl_119_21_1396a_xx_line_structure.py build --base data/corpus
```

`--olrc-zip` reads the OLRC zip from another place (its SHA-256 is still checked). This run
fetched only the released scope, so it pointed `--olrc-zip` at the content cache's object for
`28eaf347…`; the default path is fetched like any locked input.

## Encoder outline

`recognize_source_structure(body, corpus_citation_path="us/statute/42/1396a/xx")` on the
successor root body (111 lines):

| axiom-encode | Branches | By depth | Lines not starting a branch |
| --- | ---: | --- | ---: |
| `origin/main` 681c323bf (0.2.2403) | 93 | 1: 11, 2: 49, 3: 33 | 18: every item and subitem, `(aa)` … `(ee)`, `(AA)`, `(BB)` |
| same, with an uncommitted fix for subclause, item and subitem levels (in progress, not on `main`) | 111 | 1: 11, 2: 25, 3: 30, 4: 24, 5: 19, 6: 2 | 0 |

The USLM has 11 paragraphs, 25 subparagraphs, 30 clauses, 24 subclauses, 19 items and
2 subitems. With the fix, the recognized paths equal the USLM label paths (the encoder
lowercases labels). On `main` the corpus side is complete and the 18 missing branches are the
encoder's; promotion under `--require-complete-source-unit` needs the encoder fix.

## Release lines

53 tracked selectors on `main` select the released scope, among them rulespec-us's pin line
up to its newest cut, #996's `us-rulespec-2026-11-14-cms-smd-26-006` (cut on
`us-rulespec-2026-11-24-tier1-source-text`). A
successor selector swaps it for this one and changes nothing else: the citation set is the
same 12 paths (`test_the_swap_keeps_the_release_citation_set`), so release-wide citation
uniqueness cannot change. Never select both: validation rejects the pair with 12
`duplicate_release_citation` errors (`test_selecting_the_base_with_its_successor_is_rejected`).
Two selectors cut from one predecessor are a fork that `manifests/selector-lineage-baseline.yaml`
must record (`docs/release-gate-policy.md#selector-lineage`), so the swap is cut from the line's
newest selector. This change adds no selector.

## Checks run

On `origin/main` 075c5cdd8 with this branch's files, with only the released scope fetched
(`corpus fetch us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained`,
4 files from the cache, each sha256 equal to its lock entry):

- `pytest tests/test_uslm_quoted_content.py tests/test_us_pl_119_21_1396a_xx_line_structure.py`
  (`AXIOM_CORPUS_PARTIAL_TESTS=1`): 28 passed, with
  `test_structure_matches_the_codified_subsection_at_release_point_119_103` deselected because
  it reads the closure scope's zip from `data/corpus`. That test's body was run separately
  with the zip path pointed at the content cache's object (same SHA-256): passed.
- The build rewrites the scope byte for byte (two builds into scratch bases and the
  `data/corpus` build agree on every file).
- `axiom-corpus-ingest coverage … --version <this version> --write`: complete, 12 / 12; it
  writes only the git-ignored coverage file, unchanged.
- `axiom-corpus-ingest content-check` scans locked scopes only; `release_policy.scan_scope`,
  its scanner, on the unlocked successor: no findings (the released scope: none either).
- `axiom-corpus-ingest validate-release --strict-warnings` on scratch selectors under
  `complete-expression-dates-v1` (not committed): the successor alone, ok with 0 issues; the
  released scope alone, ok; both, 12 `duplicate_release_citation` errors.
- `ruff check` and `ruff format --check` on the new files, `mypy src/axiom_corpus/corpus
  --ignore-missing-imports` (108 files) and `mypy` on the script: clean.
- Not run: the whole-repository pytest suite and `validate-release` on a full swapped pin-line
  selector (both need every scope fetched).

### Round 6 verification

The offline build reproduced all four successor artifacts byte for byte. The retained USLM
has no page markers in quoted headings. Comparing `833c34ad2` and the round 6 renderer across
384 quotations and 2,579 structural elements yielded the same 2,493 render records, 42
refusals on supported tags, and 44 unsupported-tag rejections in each punctuation mode. The
comparison included the body, metadata, quote counters, and refusal messages.
The two focused pytest files passed all 60 tests in one process.

## Open questions

1. Run-in subclause (6)(A)(ii)(I): keep `(ii)` on its own line (as built), or print
   `(ii) (I) provide …` as the Statutes at Large do. The encoder reads either; one element per
   line keeps every label at a line start.
2. Metadata key names `statutes_at_large` and `margin_notes` are a proposal; no corpus
   convention exists.
3. `verification_source_paths` names a file of another locked scope. The Montana successor
   copied its verification renditions into its own sources; copying the 18,161,900-byte zip
   here would make this scope carry its own evidence at no R2 cost (the object exists), but
   every fetch of the scope would then bring the zip.

## Signing (TODO)

Not done in this change. From `docs/corpus-storage.md` "Ingest": build the scope under
`data/corpus`, then sign from a clean tracked tree; `--lock --push` writes the scope's lock,
clones its files into the cache and uploads the objects R2 lacks (the source object,
`762ae9af…`, is already locked by the released scope):

```bash
uv run --extra dev python scripts/repro/us_pl_119_21_1396a_xx_line_structure.py build --base data/corpus
AXIOM_CORPUS_INGEST_PRIVATE_KEY="$(agent-secret get agent/axiom-corpus-ingest-private-key)" \
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
  --repo . --base data/corpus \
  --jurisdiction us --document-class statute \
  --version 2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained-r2026-11-26-line-structure \
  --command 'uv run --extra dev python scripts/repro/us_pl_119_21_1396a_xx_line_structure.py build --base data/corpus (run note: docs/ingest-runs/2026-11-26-us-pl-119-21-1396a-xx-line-structure.md)' \
  --lock --push
```

One commit then carries
`.axiom/ingest-manifests/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained-r2026-11-26-line-structure.json`
and
`.axiom/corpus-locks/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained-r2026-11-26-line-structure.json`;
`axiom-corpus-ingest guard-ingested --base-ref origin/main` verifies it. After that,
`content-check us/statute/<this version>` scans the locked scope.
