# Federal CFR layer for the needs-driven closure check (2026-09-13)

The needs-driven closure check (`docs/coverage/needs-closure-2026-09-11/`) found the federal
regulation layer of six board Year 1 programs never taken: 7 CFR 271, 272, 274, 276 to 285
(SNAP; 273 and 275 were already released), 45 CFR 260 to 265 (TANF), 45 CFR 96 subpart H
(LIHEAP), 42 CFR 406, 407, 408, 423 (Medicare), 42 CFR 447 subpart A (Medicaid cost sharing),
26 CFR part 31 and the individual-income-tax sections of 26 CFR part 1 the tax report lists.
This run takes all of it from the eCFR Versioner API with the repo's `inventory-ecfr` and
`extract-ecfr` commands. Everything here is local and unsigned: the artifacts are under
`data/corpus` on the controller's machine only and nothing under `data/corpus` is committed.

Branch `discovery/ingest-federal-cfr-layer`, cut from `origin/main` (8dc613000), worked in a
sparse worktree (`~/axiom-corpus-worktrees/federal-cfr-2`, `data/corpus` excluded, no symlink)
with every extraction pointed at `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`.
GitNexus MCP tools were not available in this session; the impact analysis CLAUDE.md asks
for before editing `src/axiom_corpus/corpus/ecfr.py` was done by hand (see "Adapter change").

## Publisher and source date

eCFR Versioner API only (`https://www.ecfr.gov/api/versioner/v1/`), the primary publisher
used by every released eCFR scope; no republication, mirror or archived copy was consulted.
`titles.json` on 2026-09-13 reported `up_to_date_as_of: 2026-09-10` for titles 7, 26, 42
and 45 (latest amendments 2026-09-09, 2026-09-08, 2026-08-13 and 2026-08-31), so every scope
uses `--as-of 2026-09-10 --expression-date 2026-09-10`, the same convention as the 2026-09-11
follow-on parts (requested date = the title's served date). Version prefix `2026-09-13`; the
run-id builder appends `-title-<t>-part-<p>`.

## Collision check before extracting

The selection is `docs/ingest-runs/2026-09-13-us-rulespec-followup-union.selector.json`
(branch `release/2026-09-13-followup`, 556 scopes). Its twelve `us/regulation` scopes carry
2,161 citation paths under `us/regulation/{7/246, 7/247, 7/273, 7/275, 20/416, 26/1, 42/431,
42/435, 42/436, 42/438, 42/457, 42/600, 45/98, 45/1302, 47/54}` plus the `recovery/...` block
paths; no title-level (`us/regulation/7`) or root rows exist. A grep of every provisions JSONL
under `data/corpus/provisions` (all jurisdictions) for the target parts found exactly one
overlap: `us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1` (released) holds
the container `us/regulation/26/1` and `us/regulation/26/1/1401-1`. Everything else in scope
here was in no scope on disk. Resolution for 26 CFR part 1 is in its section below.

## Scopes taken

Every scope: coverage complete, 0 missing, 0 extra, no duplicate citation path, every section
body non-empty (one publisher placeholder, noted under part 1), all rows `source_as_of` and
`expression_date` 2026-09-10. "Units" is the eCFR structure count of live part, subpart,
section and (where taken) appendix nodes; reserved nodes are skipped and subject groups are
not emitted, the same shape as the released eCFR scopes. Seconds are `inventory-ecfr` +
`extract-ecfr` wall clock.

### 7 CFR 271, 272, 274, 276 to 285: SNAP (closure `snap_cfr_<part>_<n>`, 126 elements)

| Scope (`us/regulation/`) | Units = rows | Shape | Body chars (min/max/total) | s |
| --- | ---: | --- | --- | ---: |
| `2026-09-13-title-7-part-271` | 10 | part + 9 sections | 342 / 38,985 / 72,637 | 8+2 |
| `2026-09-13-title-7-part-272` | 19 | part + 18 sections | 1,101 / 154,201 / 286,521 | 1+2 |
| `2026-09-13-title-7-part-274` | 9 | part + 8 sections | 1,516 / 48,488 / 121,968 | 1+2 |
| `2026-09-13-title-7-part-276` | 8 | part + 7 sections | 1,070 / 11,272 / 32,717 | 1+2 |
| `2026-09-13-title-7-part-277` | 19 | part + 17 sections + Appendix A | 425 / 32,348 / 99,668 | 1+3 |
| `2026-09-13-title-7-part-278` | 9 | part + 8 sections | 1,449 / 53,171 / 114,831 | 1+3 |
| `2026-09-13-title-7-part-279` | 11 | part + 2 subparts + 8 sections | 336 / 2,291 / 12,354 | 2+3 |
| `2026-09-13-title-7-part-280` | 2 | part + 1 section | 1,288 | 2+1 |
| `2026-09-13-title-7-part-281` | 11 | part + 10 sections | 368 / 5,455 / 23,425 | 2+4 |
| `2026-09-13-title-7-part-282` | 3 | part + 2 sections | 501 / 1,831 / 2,332 | 1+2 |
| `2026-09-13-title-7-part-283` | 36 | part + 3 subparts + 32 sections | 127 / 14,437 / 74,929 | 1+2 |
| `2026-09-13-title-7-part-284` | 2 | part + 1 section | 6,735 | 1+4 |
| `2026-09-13-title-7-part-285` | 6 | part + 5 sections | 653 / 4,640 / 9,674 | 1+2 |

145 rows, 126 sections: exactly the 126 non-reserved sections `cfr_structure.py` and the SNAP
matrix count (reserved 277.15, 278.8, 278.10, 284.2 skipped). Closure elements closed:
`snap_cfr_271_1` to `_9`, `snap_cfr_272_1` to `_18`, `snap_cfr_274_1` to `_8`,
`snap_cfr_276_1` to `_7`, `snap_cfr_277_1` to `_14` and `_16` to `_18`, `snap_cfr_278_1` to
`_7` and `_9`, `snap_cfr_279_1` to `_8`, `snap_cfr_280_1`, `snap_cfr_281_1` to `_10`,
`snap_cfr_282_1`, `_2`, `snap_cfr_283_1` to `_32`, `snap_cfr_284_1`, `snap_cfr_285_1` to `_5`
(all 126 `federal_regulation | EXTRACTABLE` rows of `snap-matrix.csv`). Part 277's
"Appendix A to Part 277, Principles for Determining Costs Applicable to Administration of the
Program by State Agencies" is the part-scoped shape `--include-appendices` supports and is
taken (`us/regulation/7/277/appendix-a`, 41,687 characters). Still missing for SNAP after this
run: nothing in the federal regulation family; the `fns_guidance` rows (`snap_g09` to
`snap_g12`, `snap_g15`, `snap_g16`) are another agent's guidance run.

### 45 CFR 260 to 265: TANF (closure `tanf-f-cfr-<section>`, 128 elements)

| Scope | Units = rows | Shape | Body chars (min/max/total) | s |
| --- | ---: | --- | --- | ---: |
| `2026-09-13-title-45-part-260` | 27 | part + 3 subparts + 23 sections | 124 / 12,806 / 43,646 | 2+2 |
| `2026-09-13-title-45-part-261` | 52 | part + 8 subparts + 43 sections | 116 / 6,805 / 59,175 | 1+4 |
| `2026-09-13-title-45-part-262` | 9 | part + 8 sections | 92 / 4,884 / 19,327 | 1+2 |
| `2026-09-13-title-45-part-263` | 22 | part + 3 subparts + 18 sections | 149 / 4,739 / 19,534 | 1+2 |
| `2026-09-13-title-45-part-264` | 30 | part + 3 subparts + 26 sections | 143 / 3,581 / 22,551 | 1+2 |
| `2026-09-13-title-45-part-265` | 11 | part + 10 sections | 88 / 8,942 / 26,902 | 2+3 |

151 rows, 128 sections = the 128 `federal regulation | EXTRACTABLE` rows of `tanf-matrix.csv`
(`tanf-f-cfr-260.10` to `-265.10`; 23 + 43 + 8 + 18 + 26 + 10). No reserved node, no
appendix. Still missing for TANF at the federal level: `tanf-f-acf-guidance` (ACF OFA
guidance, REVIEW), not a regulation.

### 45 CFR 96: block grants, subpart H LIHEAP (closure `LIHEAP-F-CFR96-96-80` to `-89`)

- The adapter selects by part or by exact `--section`, not by subpart. Subpart H's eight live
  sections could have been taken with eight `--section` flags, but the whole part (73 live
  sections, 12 subparts, Appendix A "Uniform Definitions of Services"; 6 reserved sections and
  the reserved Appendix B skipped) costs the same 3 s and gives the block-grant procedures
  (subparts A to F: applications, financial management, tribal direct funding, enforcement,
  hearings) that subpart H cross-references. Scope `2026-09-13-title-45-part-96`, 87 rows,
  bodies 53 to 13,226 characters (148,689 total), 1+3 s. Subpart H is
  `us/regulation/45/96/subpart-H` with `us/regulation/45/96/80` to `/89` beneath it.
- Closure elements: the schema's ten ids `LIHEAP-F-CFR96-96-80` to `-96-89` map onto the eight
  live sections 96.81 to 96.86, 96.88 and 96.89 (`us/regulation/45/96/81` etc.); 96.80 and 96.87
  are reserved in the 2026-09-10 structure and have no text at the publisher, so
  `LIHEAP-F-CFR96-96-80` and `-96-87` should be re-marked N/A or ABSENT rather than EXTRACTABLE
  when the matrix is rebuilt. The other eight are closed. Appendix A
  (`us/regulation/45/96/appendix-a`, 19,306 characters) is taken as well.

### 42 CFR 406, 407, 408, 423: Medicare (closure `MED-F-CFR-406`, `-407`, `-408`, `-423-B`, `-423-D`, `-423-P`)

| Scope | Units = rows | Shape | Body chars (min/max/total) | s |
| --- | ---: | --- | --- | ---: |
| `2026-09-13-title-42-part-406` | 30 | part + 4 subparts + 25 sections | 301 / 8,990 / 71,686 | 2+1 |
| `2026-09-13-title-42-part-407` | 33 | part + 4 subparts + 28 sections | 371 / 9,061 / 53,183 | 2+2 |
| `2026-09-13-title-42-part-408` | 58 | part + 8 subparts + 49 sections (408.4 reserved) | 186 / 7,064 / 61,444 | 1+2 |
| `2026-09-13-title-42-part-423` | 360 | part + 25 subparts + 334 sections (2 reserved subparts, 3 reserved sections) | 74 / 53,073 / 1,174,292 | 2+5 |

All six Medicare regulation elements closed (subparts B, D and P of part 423 are
`us/regulation/42/423/subpart-B`, `-D`, `-P`). Still missing at the federal level: nothing in
the regulation family; `MED-F-CFR-435-MSP` was already PRESENT.

### 42 CFR 447: Medicaid payments, subpart A cost sharing (closure `M-447-1` to `M-447-90`, 22 elements)

Whole part for the same reason as 45 CFR 96 (no subpart selector): scope
`2026-09-13-title-42-part-447`, 79 rows = part + 7 live subparts + 71 sections (subparts D and H
and 447.58 reserved), bodies 72 to 22,868 characters (241,450 total), 2+2 s. Subpart A is
`us/regulation/42/447/subpart-A` with its 22 sections (447.1 to 447.90) beneath it; all 22
`M-447-*` elements closed. The seven `federal statute` rows of the Medicaid matrix
(`M-ST-1396a-a3` etc.) are the U.S. Code agent's.

### 26 CFR parts 1 and 31: income tax (closure `F116` to `F132`)

What `us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1` already carries: two
rows, the part container `us/regulation/26/1` and `us/regulation/26/1/1401-1` (F128's first
half). Everything else in F116 to F132 was missing.

- Part 1 is 3,659 live sections (3,774 with reserved) in a 70 MB part XML, so it is taken in
  the adapter's section-scoped mode: the ranges the tax report lists were expanded against the
  2026-09-10 structure to 345 live sections (F116 2, F117 4, F118 2, F119 6, F120 22, F121 8,
  F122 82 + 1 reserved, F123 19, F124 12, F125 3, F126 86 + 6 reserved, F127 38, F128 43 of
  which 1.1401-1 is released, F129 9 + 1 reserved, F130 8, F132 1), and 1.1401-1 was left out
  so the new scope shares only the container with the released one. Scope
  `2026-09-13-title-26-part-1`: 344 `--section` selectors, 345 rows, coverage complete,
  bodies 0 to 179,160 characters (5,695,123 total), 2+33 s. Sources: `title-26-part-1.xml`
  70,106,353 bytes sha256 `cbad1cf646425f85f951a0be49e2e103590cebd31e74b8f77059aa5e213ded5b`
  (the section-scoped mode retains the part XML and the formula graphics, not the 2 MB
  structure JSON).
- The one empty body is the publisher's: `§ 1.163-16` is an eCFR placeholder (heading `xxx`,
  content only "Link to an amendment published at 91 FR 57235, Sept. 8, 2026"), so the corpus
  row is empty because the source is. Re-take part 1 after the amendment's effective date.
- Six formula images were archived without transcriptions (`ecfr/graphics/`: four in 1.162-28,
  one in 1.163-10T, one in 1.408-11); their sections' text bodies are complete apart from the
  image-only formulas. Reviewed transcriptions can be supplied with `--graphic-transcriptions`.
- F132's other half, 26 CFR 301.7701-18 (part 301, procedure and administration), is outside
  the work order and not taken. F131 lists 31.3101-1 to 31.3402(r)-1; the whole of part 31 is
  taken instead: scope `2026-09-13-title-26-part-31`, 359 rows = part + 7 subparts + 351
  sections (31.3121(a)(12)-1 reserved skipped), bodies 62 to 166,202 characters (1,763,822
  total), 4+3 s, `title-26-part-31.xml` 2,039,543 bytes sha256
  `8d5156d440caefafd6586c2f2e4feca124422faf51e50f12da7b3fc1ee0266d0`.
- Elements closed: F116, F117, F118, F119, F120, F121, F122, F123, F124, F125, F126, F127, F129,
  F130, F131, the 1.1402(a)-1 to 1.1402(h)-1 half of F128 and the 1.7703-1 half of F132.

#### Collision and resolution: the `us/regulation/26/1` container

Both part 1 scopes carry the container row, and a selector cannot carry a path twice. The
released scope is untouched; `scripts/consolidate_release_scopes.py` (the 2026-09-11 mechanism)
built one successor:

```bash
uv run python scripts/consolidate_release_scopes.py --base data/corpus \
  --jurisdiction us --document-class regulation \
  --source-version 2026-07-24-1401-coordination-repair-title-26-part-1 \
  --source-version 2026-09-13-title-26-part-1 \
  --target-version 2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated
```

346 rows (the two container rows were structurally identical and folded; 1.1401-1 body
byte-equal to the released scope with its 2026-07-22 dates; the 344 new bodies byte-equal to
the section-scoped scope), coverage complete, 3 s, 134 MB of retained sources (both part XML
snapshots plus the graphics). The selector swaps the released scope for the successor; the
section-scoped `2026-09-13-title-26-part-1` stays on disk for provenance and is not selected.

## Adapter change: parenthesised section identifiers

Title 26 numbers many sections after the Code subsection they implement: 119 of the 345 part-1
sections and 254 of the 351 part-31 sections have identifiers like `1.401(k)-1`,
`31.3121(a)(1)-1` or `31.3121(a)-1T`. Before this run the adapter's section regex
(`[0-9A-Za-z][0-9A-Za-z.-]*`) stopped at the first parenthesis: the inventory skipped such
sections (`fullmatch` failed) and the XML pass truncated them (`search` gave `1.401` for
`1.401(k)-1`), so a whole-part run would have emitted colliding `us/regulation/26/1/401` paths
and section-scoped selectors could not name them. Parentheses are also outside the
citation-path segment character set (`schema/citation-path.v1.json`).

Change (`src/axiom_corpus/corpus/ecfr.py`): one shared `_SECTION_IDENTIFIER_PATTERN` that
admits `(` and `)`, and `_section_path_segment`, which folds each parenthesised group into
hyphens for the path only (`401(k)-1` -> `401-k-1`, `3121(a)(1)-1` -> `3121-a-1-1`,
`3121(a)-1T` -> `3121-a-1T`). Citation label, `legal_identifier`, `ecfr:section`, metadata and
the reader URL keep the official form. Hand impact analysis: the three parsers
(`_section_citation_from_identifier`, `_section_citation_from_element`, the selector check in
`_filter_ecfr_inventory_sections`) are called only inside `ecfr.py`, from the inventory
walker, `_scoped_structure_from_part_xml`, `_element_citation_path` and `_section_provision`;
behaviour changes only for identifiers the old regex skipped or truncated. No released eCFR
scope and none of the 25 title 7/42/45 scopes above has such an identifier (checked against
the 2026-09-10 structures), so their paths are unchanged. Three unit tests cover the inventory
fold, the selector and the XML parse; `ruff check` and `mypy` pass on the module;
`docs/corpus-pipeline.md` records the rule. The 79 slugged segments with an uppercase letter
(`36B-1`, `170A-1`, `3121-a-1T`; 69 in part 1, 10 in part 31) count toward the citation-path
schema's `uppercase_segments` ratchet, which CI measures over tracked provisions, so the
baseline needs ratcheting at the artifact commit, as the 2026-09-12 release did.

## Draft selector validation

Draft = the follow-up selector plus the new scopes, built in the session scratch directory and
validated from the worktree after each title:

```bash
uv run axiom-corpus-ingest validate-release \
  --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release <scratch>/draft-federal-cfr-layer.selector.json --ignore-r2-missing --max-issues 600
```

| Draft | Scopes | Result | s |
| --- | ---: | --- | ---: |
| + 13 title 7 scopes | 569 | `ok: true`, 0 errors, 546 warnings | 54 |
| + 7 title 45 and 5 title 42 scopes | 581 | `ok: true`, 0 errors, 546 warnings | 81 |
| + part 31, released 1401 scope swapped for its successor | 582 | `ok: true`, 0 errors, 546 warnings | 39 |

The 546 warnings are exactly the consolidation note's set (541 `missing_parent_id` in
`us-ca/regulation/2026-07-13-recovery`, 5 advisory `unsectioned_document_body` in GA, KY, MD,
OR WIC and IA tax); no issue names a `2026-09-13` or `title-26` scope, and no
`duplicate_release_citation`.

## Queue rows

`scripts/build_federal_cfr_layer_queue_rows.py` (new, idempotent, `--base` checks its counts
against the coverage files) writes one `agent_ready` `federal_regulation_ecfr` row per taken
scope after each queue's existing federal rows, mirroring the 2026-09-11 rows
(`target_manifest: null`, `index_url` the 2026-09-10 structure JSON, `index_document_count` =
`taken_count` = rows), appends a one-sentence pointer to the pre-existing federal row and
recomputes `status_counts`. Queues: `snap-completion-agent-queue.yaml` (13 rows; the SNAP
queues had no federal row, so these are first), `tanf-agent-queue.yaml` (6),
`liheap-agent-queue.yaml` (1), `medicare-agent-queue.yaml` (4), `medicaid-agent-queue.yaml`
(1), `tax-agent-queue.yaml` (2: the consolidated successor and part 31). `agent_ready` counts:
SNAP 7 to 20, TANF 26 to 32, LIHEAP 55 to 56, Medicare 1 to 5, Medicaid 42 to 43, Tax 21 to 23.

The Medicaid generator already carried later `us` rows through untouched (territories rebase);
the TANF, LIHEAP, Medicare, tax and SNAP-completion generators keyed rows by jurisdiction and
would have dropped them, so each now collects later rows per jurisdiction and writes them back
after the first (`extra_rows`). Checked without fetching: the LIHEAP `--territories --only us-pr`
and Medicare `--territory-rows --only us-pr` modes leave the queues byte-identical, and a second
run of the new generator changes nothing.

## Commands

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for tp in "7 271" "7 272" "7 274" "7 276" "7 277" "7 278" "7 279" "7 280" "7 281" "7 282" "7 283" \
          "7 284" "7 285" "45 260" "45 261" "45 262" "45 263" "45 264" "45 265" "45 96" \
          "42 406" "42 407" "42 408" "42 423" "42 447" "26 31"; do set -- $tp
  APP=""; case "$1/$2" in 7/277|45/96) APP=--include-appendices;; esac
  uv run axiom-corpus-ingest inventory-ecfr --base $B --version 2026-09-13 --as-of 2026-09-10 \
    --only-title $1 --only-part $2 $APP
  uv run axiom-corpus-ingest extract-ecfr --base $B --version 2026-09-13 --as-of 2026-09-10 \
    --expression-date 2026-09-10 --only-title $1 --only-part $2 --workers 2 $APP
done
# 26 CFR part 1: the 344 selectors expanded from the tax report's ranges, e.g.
uv run axiom-corpus-ingest extract-ecfr --base $B --version 2026-09-13 --as-of 2026-09-10 \
  --expression-date 2026-09-10 --only-title 26 --only-part 1 --workers 2 \
  --section 1.1-1 --section 1.2-2 --section 1.21-1 ... --section '1.401(k)-1' ... --section 1.7703-1
```

Disk: 21 GB free at the start, 7.3 GB at the end; the run itself added about 480 MB (twenty-six
retained title structure JSONs of 2 to 12 MB, two 70 MB part-1 XML copies in the consolidated
scope). The rest was other agents' concurrent writes into `data/corpus` (CHIP state plans, FNS
and Medicare guidance, U.S. Code scopes); `df` was checked before every part and never fell
below the 3 GB stop line.

## Checks

- `uv run ruff check scripts`: passes. `ruff check` and `mypy` on `ecfr.py` and its test file:
  pass.
- `uv run --extra dev pytest -q tests/test_corpus_ecfr.py`: 104 passed, 7 failed; the 7 are
  the retained-snapshot tests the 2026-09-11 note lists (`test_retained_416_default_scope_ignores_unsupported_appendix`
  x6, `test_iter_ecfr_title_provisions_preserves_mixed_part_parentage_and_bodies`), which open
  `data/corpus` files the sparse worktree does not have.
- `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or ecfr"`
  in the sparse worktree: 441 passed, 2 skipped, 21 failed, 52 s. The 21 are exactly the
  sparse-worktree set the 2026-09-11 note lists (`FileNotFoundError` on retained `data/corpus`
  sources): the seven above, two `test_recover_ingest` `ecfr-xml` parametrizations (retained
  275 and 1302 XML), `test_be_rulespec_2026_08_23_promotion`, two in
  `test_build_ny_tanf_compatibility_scope`, `test_rulespec_be_source_promotion`, the AK, CT,
  MI, MT, ND and NY SNAP manual tests, `test_armenia_arlis` and `test_israel_openlaw`. The same
  selection passes in a full checkout.

## Controller

Selector additions (26 new scopes) and one swap; no unreleased scope dropped:

```json
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-271"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-272"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-274"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-276"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-277"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-278"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-279"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-280"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-281"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-282"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-283"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-284"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-7-part-285"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-260"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-261"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-262"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-263"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-264"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-265"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-45-part-96"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-42-part-406"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-42-part-407"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-42-part-408"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-42-part-423"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-42-part-447"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-13-title-26-part-31"}
```

Swap: `us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1` (released) out,
`us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated`
in. Do not also select `2026-09-13-title-26-part-1`.

1. Merge this branch (adapter change, its tests, the queue generator and five generator
   patches, six queues, two changelog fragments, docs). The adapter change is required to
   regenerate the two title 26 scopes and for any future title 26 `extract-ecfr` run.
2. Apply the additions and the swap to the follow-up draft (556 to 582 scopes) and re-run
   `validate-release --ignore-r2-missing`; expect `ok: true`, 0 errors, 546 warnings.
3. Ratchet `schema/citation-path.v1.json` `uppercase_segments` by 79 at the artifact commit.
4. Sign with `scripts/sign_release_scopes.sh`; the 27 scopes add about 480 MB of sources
   (the two 70 MB part-1 XML copies dominate) and 12 MB of provisions.
5. Decisions left open: (a) whether the LIHEAP and Medicaid work orders want whole parts 96 and
   447 in the release or subpart-only successors (a subpart-scoped successor would be a
   `--section` list run, 3 s); (b) 26 CFR 301.7701-18 for F132 (part 301 not in the work
   order); (c) re-taking 26 CFR 1.163-16 once 91 FR 57235 takes effect; (d) transcriptions for
   the six formula images; (e) re-running the tax, SNAP, TANF, LIHEAP, Medicare and Medicaid
   matrix builders against the new scopes so the closure percentages move.
