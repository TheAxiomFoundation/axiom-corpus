# eCFR table captions (2026-10-12)

The eCFR adapter's `_table_text` (`src/axiom_corpus/corpus/ecfr.py`) read only `TR`
rows, so every table's `<CAPTION>` was dropped from provision bodies. The Sol review of
axiom-corpus#826 found it (run note `docs/ingest-runs/2026-10-12-oasdi-ssa-sources.md`
on that branch): 20 CFR 404.1592 kept the rows of its two tables, which share the
header `For months` and the same year column, but lost "Table 1—For Employees" and
"Table 2—For the Self-Employed", the only text that says which table applies to whom.

## Behaviour

`_table_text` now walks the table in document order and, on reaching a `CAPTION`,
emits `_table_caption_lines(caption)`:

- A caption made only of `P` children, with no loose text, gives one line per
  non-blank paragraph, in source order. This covers every caption in the retained
  eCFR sources: 1,546 captions in the 48 distinct eCFR XML files, shaped `P.title`
  (1,057), `P.title` + `P.headnote` (423), `P.headnote` (51), `P.title` + two
  headnotes (12), and two `P.title` (3). eCFR puts `CAPTION` first in `TABLE` in all
  1,546, so caption lines open the table block, before the header row.
- Any other shape (loose text, inline markup directly in `CAPTION`, text mixed with
  `P`) is kept whole as one line, so no caption text is dropped or split.
- A blank or empty caption adds nothing; a caption-only table now yields a block
  where it used to vanish.

Inline markup (`E`, `strong`, `sup`) is flattened with `_element_text`, as for cells
and paragraphs. Row output is unchanged.

## Impact analysis (by hand)

GitNexus was unavailable on 2026-10-12 (database version mismatch), so the blast
radius was traced with `git grep` at `origin/main` 56592c88b.

| Depth | Symbol | Where | Effect |
| --- | --- | --- | --- |
| d=1 | `_section_body` | `ecfr.py:1026`, the only caller of `_table_text` | Section and appendix bodies with a captioned table gain the caption lines |
| d=2 | `_section_provision`, `_appendix_provision` | `ecfr.py:1380`, `ecfr.py:1442` (`appendix=True`) | Same, per record |
| d=3 | `iter_ecfr_title_provisions` | `ecfr.py:1485` | Every eCFR extraction path below |
| d=4 | `_extract_one_title` → `_extract_title_results` → `extract_ecfr` → `axiom-corpus-ingest extract-ecfr` | `ecfr.py:2037`, `1952`, `1629`; `cli.py:1290` | New eCFR ingests carry captions |
| d=4 | `scripts/recover_ingest.py:268`, `scripts/recover_ingest_batch.py:990` | recovery replays of eCFR XML | Recovered eCFR sections carry captions (7 CFR 246 came this way) |
| d=4 | `scripts/repro_us_cfr_416_deeming_slice.py:235` | pinned replay of the July part 416 slice | Unaffected; see the replay plan |

Not affected: the same-named `_table_text` in `illinois_admin_code.py` and
`ohio_admin_code.py` (separate BeautifulSoup functions); `documents.py`,
`federal_register.py`, and the legacy `converters/ecfr.py`, none of which call this
adapter (the legacy converter flattens whole elements with `itertext`, so it never
dropped captions). Downstream, `anchors.py` reads paragraph heads at line starts
(`_HEAD`); none of the 40 affected records' captions begins with a parenthesized label,
and no anchor file covers any of them. Across the 48 distinct retained files, 25
caption paragraphs do begin with one (for example `(A) Computation of Net Shortfall
Charge…` in 26 CFR 1.412(c)(1)-2), all in sections no scope stores yet; when such a
section is extracted, its anchors should be checked for a caption read as a
paragraph head.

## Differential replay over every retained eCFR source

With the whole corpus fetched, every eCFR XML under `sources/us/regulation` (54
files, 48 distinct, including nested copies inside consolidated scopes and the
recovery scope's `official-documents/`) was extracted twice, with `origin/main`'s `_table_text` and with
this branch's, for every part in the file and appendices included (the three files
whose appendix identifiers the adapter refuses were extracted without appendices):

- 27,881 provisions; 689 change. The changed set equals, in every file, the set of
  provisions that hold a captioned table.
- Every change is insert-only, and the inserted non-blank lines are exactly that
  provision's caption lines (checked with a line diff, not substring search).
- No caption sits outside a section or appendix.

The replay script and its output are kept with the review evidence
(`~/reviews/ecfr-table-captions-2026-10-12/caption_diff.py`, `caption_diff.json`).

## Replay plan for released scopes

This PR re-extracts nothing. Released scopes are immutable versions.

- **Part 416 deeming slice.** `tests/test_repro_us_cfr_416_deeming_slice.py`
  regenerates the 14-path slice with the current adapter and checks the pinned
  hashes in `docs/validation/us-cfr-416-deeming-baseline.json`. The retained July
  XML has two captions, in 416.974 and 416.1112, both outside the slice, and the
  slice's container bodies join only the slice's own children. The test passes
  unchanged on this branch, so the baseline needs no edit and no versioned adapter
  behaviour. `test_deeming_slice_replay_holds_no_captioned_table` records why.
- **Other released scopes.** A replay of a released scope pins a producer commit
  and its locked environment, as the part 416 baseline does (producer
  `f22e9a458`), rather than running at a later `HEAD`. The signed ingest manifest's
  `axiom_corpus_git.commit` is the `HEAD` of the checkout that signed it
  (`_git_metadata`, `ingest_manifests.py:1377`), which can postdate extraction, so it
  is a starting point, not proof of the producer. For the 40 records below,
  `origin/main` 56592c88b is a producer: its adapter reproduces every stored body
  from the retained XML. No test replays those scopes at `HEAD`; the full suite
  passes on this branch.
- **Why not an opt-in flag.** The California LegInfo fix shipped as
  `--preserve-tables`, off by default. A default-off caption flag would keep `HEAD`
  replays of the nine scopes byte-identical, but no test replays them at `HEAD`, and
  it would leave every new eCFR ingest dropping captions unless the flag were
  remembered.

## Successor candidates

`scripts/audit_ecfr_table_captions.py` re-extracts each stored `ecfr-xml` record that
holds a captioned table from its retained bytes and compares it with the stored
body. Its report is `ecfr-table-captions-2026-10-12.audit.json`. Nine released
scopes, 40 records and 237 caption lines are missing; in every record the
re-extraction differs from the stored body only by inserted caption lines. A second,
independent method (the differential replay above, mapped onto stored records)
finds the same 40 records and caption lines. No unreleased scope on `main` is
affected, and no container body is.

Selected by the newest US selector, `us-rulespec-2026-10-11-w5-remainder-union`:

| Scope (`us/regulation/…`) | Records | Captions | Records and captions |
| --- | --- | --- | --- |
| `2026-06-18-title-47-part-54-r2026-07-15-self-contained` | 4 | 4 | 54.505, 54.621, 54.1708, 54.2007 ("Table 1 to Paragraph …") |
| `2026-06-24-title-45-part-1302` | 1 | 1 | 1302.21 "Table to § 1302.21(b)—Center-Based Group Size" |
| `2026-07-13-recovery-r2026-07-17-dedup` | 1 | 4 | 7 CFR 246.10, Tables 1–4 to paragraphs (e)(9)–(e)(12) (food packages and supplemental-food specifications) |
| `2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated` | 14 | 112 | 1.163-2, 1.163(j)-2, -5, -6, 1.170A-10, 1.170A-12, 1.199A-6, 1.401(l)-2, -3, -4, 1.404(a)-13, 1.414(c)-2, 1.414(c)-4, 1.414(l)-1 |
| `2026-09-11-title-20-part-416` | 2 | 2 | 416.974, 416.1112 ("Table 1") |
| `2026-09-13-title-42-part-407` | 1 | 1 | 407.25 "Table 1 to Paragraph (a)(1)(v)" |
| `2026-09-13-title-42-part-423` | 2 | 2 | 423.910, 423.2440 |

Selected only by earlier selectors (superseded in the newest by the scopes above):

| Scope (`us/regulation/…`) | Records | Captions |
| --- | --- | --- |
| `2026-06-18-title-47-part-54` | 4 | 4 |
| `2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated` | 11 | 107 |

Pending: axiom-corpus#826 adds `us/regulation/2026-10-12-title-20-part-404`, extracted
before this change. Its sections 404.1574, 404.1584 and 404.1592 hold four captions
(the other 44 captions in that file are in appendices it does not take). Re-extracting
it after this change merges, before release, avoids a tenth successor.
`test_released_scopes_missing_captions_match_the_recorded_successor_candidates` fails
if a release selector names another eCFR scope that lacks captions, and its message
says what to do.

## Reproduce

```bash
uv run axiom-corpus-ingest corpus fetch us/regulation
uv run python scripts/audit_ecfr_table_captions.py \
  --output docs/validation/ecfr-table-captions-2026-10-12.audit.json
AXIOM_CORPUS_PARTIAL_TESTS=1 uv run pytest tests/test_ecfr_table_captions.py \
  tests/test_repro_us_cfr_416_deeming_slice.py
```
