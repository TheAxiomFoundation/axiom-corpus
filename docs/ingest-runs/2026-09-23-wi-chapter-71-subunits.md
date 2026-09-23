# Wisconsin chapter 71 subunits and 2025 Schedule SB instructions (2026-09-23)

Two scopes for the Wisconsin individual income tax subtractions, so that
Wis. Stat. 71.05(6)(b)9 (the 30 percent long-term capital gain subtraction) and
71.05(6)(b)54m (the 2025 Wis. Act 15 retirement income subtraction) resolve to
their own provisions, and the Department of Revenue's 2025 Schedule SB
instructions are retained next to them.

| scope | rows | coverage |
|---|---:|---|
| `us-wi/statute/2026-09-23-income-tax-subunits-chapter-71` | 5,034 | complete, 5,034 / 5,034, 0 missing, 0 extra |
| `us-wi/form/2026-09-23-wi-schedule-sb-2025` | 2 | complete, 2 / 2, 0 missing, 0 extra |

Neither scope is signed, published, loaded into Supabase or added to a release
selector.

## 1. Statute: child provisions below the section

### Problem

`us-wi/statute/2026-07-16-pit-west-chapter-71` stores Wis. Stat. 71.05 as one
100,371-character section record. Nothing below the section had a citation path,
so `us-wi/statute/71.05/6/b/54m` could not be resolved, and slicing the section
body by `(54m)`-style markers fails because Wisconsin writes subdivisions as
`54m.` and `9.`.

### What the source asserts

The Legislature's chapter page (`https://docs.legis.wisconsin.gov/statutes/statutes/71?view=section`)
publishes every numbered unit as its own `div` carrying:

- `data-path`, which extends the section's own path
  (`/statutes/statutes/71/i/05` → `/statutes/statutes/71/i/05/6/b/54m`);
- `data-cites`, the official self-citation (`statutes/71.05(6)(b)54m.`); and
- a class naming the level: `qsatxt_2subsect` (subsection (6)), `qsatxt_3para`
  (paragraph (b)), `qsatxt_4subdiv` (subdivision 54m.), `qsatxt_5subdivpara`
  (subdivision paragraph a.).

On the page retrieved for this run, all 4,918 unit `div`s have a `data-path`
under their section's path, no path repeats, every non-root unit's parent unit
exists, and each carries exactly one non-`(intro.)` self-citation that equals the
path-derived citation up to case (the publisher writes paragraph l as `(L)`).
Because the structure is identified by the publisher, the child rows follow the
assertion-frontier rule in `docs/granularity-policy-proposal.md` rather than a
heuristic split.

### Adapter change (`src/axiom_corpus/corpus/state_adapters/wisconsin.py`)

- `parse_wisconsin_chapter_page` records the section's `data-path` and builds a
  `_WisconsinSubunitBuilder` for each unit. The citation path is the section path
  plus the unit's `data-path` segments relative to the section
  (`us-wi/statute/71.05/6/b/54m`; paragraph l stays `l`, as the publisher's path
  has it). A text block without such a path, or with a segment outside
  `[A-Za-z0-9]`, stays in the section body only.
- Body: the unit's own text with its number and title removed (the title goes to
  `heading`), as the section record already does for the section number and
  title, followed by every descendant unit's line in document order with their
  numbers kept. Every child body is therefore a contiguous run of the unchanged
  section body. Editorial notes (`qsnote_*`) stay out, as they do for sections.
- Record fields: `kind` (`subsection`, `paragraph`, `subdivision`,
  `subdivision_paragraph`), `citation_label` and `legal_identifier`
  (`Wis. Stat. 71.05(6)(b)54m.`), `source_id` and `identifiers["wisconsin:citation"]`
  (the official self-citation), `parent_citation_path` / `parent_id` (nearest
  enclosing unit, else the section), `level` (section level plus depth),
  `ordinal` (position among siblings), and `metadata.data_path`,
  `metadata.official_citation`, `metadata.section`, `metadata.section_heading`,
  subchapter fields, `references_to`, `publication_note`.
- `extract_wisconsin_statutes(..., include_subunits=True)` emits each section's
  children right after the section. `include_subunits=False` keeps the section
  grain (and `parse_wisconsin_chapter_page` then skips building child units);
  `extract-state-statutes` reads it from the manifest option
  `include_subunits`. `manifests/state-statutes.pit-west-recovery.yaml` pins
  `include_subunits: false` for the released section-grain scope. The
  whole-state entry in `manifests/state-statutes.current.yaml` (version
  `2026-05-10`, in no release selector) takes the default, so a future rerun of
  it emits child rows for every chapter.
- `extract_wisconsin_publication_note` matched only the April 3, 2026
  publication. It now matches any `YYYY-YY Wisconsin Statutes updated through ...
  (Published M-D-YY)` note, falling back to `Updated through YYYY Wisconsin Act N
  ... in effect on Month D, YYYY`. A new option,
  `include_publication_note` (default true; manifest option of the same name),
  leaves `metadata.publication_note` out. The recovery manifest sets it to false,
  because the released scope was written before the parser recognised its
  July 1, 2026 note and its rows have none.
- With `source_dir` set, a missing retained file now raises `FileNotFoundError`
  instead of falling through to a live download (see Verification for the
  recovery-manifest path this exposed).

Blast radius (checked by hand; GitNexus has no index of this worktree):
`extract_wisconsin_statutes` is called only by the `wisconsin-statutes` branch of
`extract-state-statutes` in `cli.py` and by tests; `parse_wisconsin_chapter_page`,
`extract_wisconsin_publication_note` and `_WisconsinFetcher` only by the adapter
and tests.

### Extraction

```bash
uv run axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-wi-statutes-chapter-71-subunits.yaml
```

The adapter appends `-chapter-71`, so the scope version is
`2026-09-23-income-tax-subunits-chapter-71`. Both pages were fetched from the
official site on 2026-09-23 and read "2023-24 Wisconsin Statutes updated through
2025 Wis. Act 247 ... in effect on September 4, 2026 ... (Published 9-4-26)", so
`source_as_of` and `expression_date` are 2026-09-04.

| retained source | SHA-256 | bytes |
|---|---|---:|
| `sources/us-wi/statute/2026-09-23-income-tax-subunits-chapter-71/wisconsin-statutes-html/statutes/prefaces/toc.html` (`https://docs.legis.wisconsin.gov/statutes/prefaces/toc`) | `5d9d8d7626859b8f9abfd16804a463444e5eb9e103020d04e77a92519cb6494c` | 298,616 |
| `sources/us-wi/statute/2026-09-23-income-tax-subunits-chapter-71/wisconsin-statutes-html/statutes/statutes/71.html` (`https://docs.legis.wisconsin.gov/statutes/statutes/71?view=section`) | `8c72a3c9f974d1e67f622427cd64b9f2512c0902eeef45b1471f3c925e05e90e` | 4,929,719 |

Rows: 1 chapter, 16 subchapters, 99 sections, 718 subsections, 1,629 paragraphs,
1,978 subdivisions, 593 subdivision paragraphs.

### Target provisions

| citation path | kind | citation label | parent | body chars |
|---|---|---|---|---:|
| `us-wi/statute/71.05/6` | subsection | Wis. Stat. 71.05(6) | `us-wi/statute/71.05` | 55,590 |
| `us-wi/statute/71.05/6/b` | paragraph | Wis. Stat. 71.05(6)(b) | `us-wi/statute/71.05/6` | 45,759 |
| `us-wi/statute/71.05/6/b/9` | subdivision | Wis. Stat. 71.05(6)(b)9. | `us-wi/statute/71.05/6/b` | 676 |
| `us-wi/statute/71.05/6/b/54m` | subdivision | Wis. Stat. 71.05(6)(b)54m. | `us-wi/statute/71.05/6/b` | 2,000 |

`71.05/6/b/9` begins "On assets held more than one year and on all assets
acquired from a decedent, 30 percent of the capital gain ...". `71.05/6/b/54m`
holds subdivision paragraphs a. through e. (the payments subtraction for taxable
years beginning after December 31, 2024; age 67; $24,000, or $48,000 for a joint
return when both spouses are 67; no s. 71.07 credit in the same year; the
part-year-resident proration and nonresident bar), each also a child row
(`71.05/6/b/54m/a` ... `/e`).

### Verification

- Every child body (4,918) equals an independent re-derivation with `lxml` from
  the retained chapter HTML (unit text without its number, title and hidden
  reference anchor, then descendants in document order): 0 mismatches.
- Against `us-wi/statute/2026-07-16-pit-west-chapter-71`: all 116 released
  citation paths are present; all 116 bodies are byte-identical; the only field
  differences are `version`, `source_path`, `source_as_of`, `expression_date`
  and `metadata.publication_note` (now set). The chapter HTML differs from the
  July 1, 2026 snapshot only in its publication date lines and the placement of
  one editorial note under s. 71.47.
- Rerunning `manifests/state-statutes.pit-west-recovery.yaml` for
  `us-wi-statutes` (`--only-source-id us-wi-statutes`, scratch base) reproduces
  all five files the signed ingest manifest
  `.axiom/ingest-manifests/us-wi/statute/2026-07-16-pit-west-chapter-71.json`
  lists, byte for byte (provisions `af1b3afb…`, inventory `16d17044…`, coverage
  `2776dc79…`, TOC `6cd0fcef…`, chapter `662f8ba8…`), with no network access.
  `tests/test_corpus_wisconsin.py::test_pit_west_recovery_manifest_replays_the_signed_wisconsin_scope`
  runs that replay against the git-tracked retained bytes and fails if any hash
  moves; with `include_publication_note` flipped to true it fails on the
  provisions hash (`2e9c4b45…`). Before this change that
  rerun did not read the retained bytes at all: the manifest's `source_dir` ended
  in `/wisconsin-statutes-html`, the adapter's relative paths already start with
  `wisconsin-statutes-html/`, no file matched, and the fetcher silently downloaded
  the live September 4 pages instead. `source_dir` now names the scope directory,
  and the adapter raises `FileNotFoundError` when a `source_dir` run misses a file
  rather than falling back to the network (the Oregon adapter already behaves
  this way).
- Re-extracting from this scope's retained sources (`source_dir` =
  `data/corpus/sources/us-wi/statute/2026-09-23-income-tax-subunits-chapter-71`)
  and rerunning the manifest from the download cache both reproduce the
  provisions, inventory and coverage files byte for byte. The two official pages
  fetched again on 2026-09-23 at 12:17 EDT hash to the same SHA-256 values as the
  retained copies.
- Coverage command (`axiom-corpus-ingest coverage ... --write`): complete, 5,034
  matched.
- `scripts/validate_citation_paths.py --provisions <tree with only the new file>`:
  5,034 records, 5,034 unique paths, 0 irregular segments, `RESULT: OK`.
- `validate_release` on a scratch selector (not committed) holding the 16 `us-wi`
  scopes of `us-rulespec-2026-09-14-wave4-r2-union`, with the statute scope
  swapped for this one and the Schedule SB scope added, under
  `complete-expression-dates-v1`: 17 scopes, 0 errors, 0 warnings.

Note on the released scope: its retained TOC and chapter pages read
"(Published 7-1-26)" and "in effect on July 1, 2026", while its rows carry
`source_as_of` and `expression_date` 2026-04-03 from the recovery manifest. This
change leaves those dates alone so that the released version replays exactly;
the recovery manifest's comment records the mismatch and says that any
correction belongs in a new version, never in place.

## 2. Form: 2025 Schedule SB instructions

`manifests/us-wi-2025-schedule-sb-instructions.yaml` follows the Form 1-ES
pattern (`manifests/us-wi-2026-form1-es-instructions.yaml`): one PDF,
`segmentation: single_block`, citation path
`us-wi/form/individual-income-tax/2025/schedule-sb-instructions`.

```bash
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-09-23-wi-schedule-sb-2025 \
  --manifest manifests/us-wi-2025-schedule-sb-instructions.yaml
```

- Source: <https://www.revenue.wi.gov/TaxForms2025/2025-ScheduleSB-Inst.pdf>,
  retrieved 2026-09-23 (HTTP `Last-Modified: Fri, 07 Nov 2025 15:50:57 GMT`),
  17 pages, document I-0104 (R. 10-25), 390,191 bytes, SHA-256
  `4ebf3e36a2740ed7c1146c3e2b43b3d3762d3d5601ea6be5b70d2262b7a18494`, retained at
  `sources/us-wi/form/2026-09-23-wi-schedule-sb-2025/official-documents/us-wi-dor-2025-schedule-sb-instructions.pdf`.
  The `-inst.pdf` spelling serves the same bytes, and the host without `www.`
  redirects to `www.` and the same bytes. Fetched again on 2026-09-23 at
  12:17 EDT: same SHA-256; `pdfinfo` reports 17 pages, title "2025 I-0104 2025
  Schedule SB Instructions - Subtractions from Income".
- Rows: the document root and `.../schedule-sb-instructions/document-1`, whose
  74,474-character body holds all 17 pages, including "Line 5 – Capital
  Gain/Loss Subtraction" and "Line 16 – Retirement Income Subtraction (Credits
  Restricted)".
- `source_as_of` 2026-09-23 (retrieval), `expression_date` 2025-01-01 (tax year
  2025), as the tax-year-2025 form manifests for Georgia IT-511 and the
  California 2025 tax materials do.
- A rerun of the manifest into a scratch base re-downloads the PDF and
  reproduces the source, inventory, provisions and coverage files byte for byte.
- Metadata records the line 5 and line 16 statements, checked against the PDF
  text. The instructions describe themselves as statements or interpretations of
  ch. 71, Wis. Stats., and sec. Tax 3.01, Wis. Adm. Code, enacted as of
  October 6, 2025. The intake does not certify final-return liability, RuleSpec
  semantics or PolicyEngine parity.

## Release selection

A later named release that should carry these rows selects

```json
{"jurisdiction": "us-wi", "document_class": "statute", "version": "2026-09-23-income-tax-subunits-chapter-71"},
{"jurisdiction": "us-wi", "document_class": "form", "version": "2026-09-23-wi-schedule-sb-2025"}
```

and drops `{"us-wi", "statute", "2026-07-16-pit-west-chapter-71"}`, whose 116
paths the new scope carries with identical bodies. Profiled releases
(`complete-expression-dates-v1`) reject a citation path owned by two scopes.

## Checks

Run on the final tree before committing:

| check | result |
|---|---|
| `uv run --extra dev ruff check .` | all checks passed |
| `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports` | no issues in 93 source files |
| `pytest tests/test_corpus_wisconsin.py tests/test_corpus_cli.py` | 83 passed |
| `pytest tests/test_ingest_manifest_provenance.py tests/test_citation_path_grammar.py` | 57 passed |
| recovery replay test with `include_publication_note: true` (sensitivity check) | fails on provisions `2e9c4b45…`, as intended |
| new statute scope re-extracted from its retained bytes, scratch base | 5,034 rows; all five files byte-identical |
| `towncrier check --compare-with origin/main` | the three fragments found |

The whole-repository `pytest -q` run was not part of this change. `ruff format
--check` flags the four touched Python files, but their origin/main versions already
fail it, and CI does not run it. `guard-ingested` needs
`AXIOM_CORPUS_INGEST_PUBLIC_KEY`, and the new scopes are unsigned (see below).

## Remaining controller steps

`sign-ingest-manifest` for both scopes after the commit (CI `guard-ingested`
fails until then), then selector, dry-run, publish and activation as usual.
`data/` is ignored by `.gitignore`, so the artifacts need `git add -f`;
`data/corpus/downloads/` must not be added.
