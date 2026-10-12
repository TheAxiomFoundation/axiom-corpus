# 20 CFR part 404 with its subpart appendices

Date: 2026-10-12 (extraction 18:31 to 18:32 UTC)
Branch: `ingest/cfr-404-subpart-appendices`, cut from `origin/main` (2b9ca4ba2).
Follows: `docs/ingest-runs/2026-10-12-oasdi-ssa-sources.md` (PR #826).

## Why

The part 404 scope of PR #826, `us/regulation/2026-10-12-title-20-part-404`, has the part,
its 21 subparts and 788 sections, but none of the part's 11 appendices. All 11 are
subpart-scoped, and `extract-ecfr --include-appendices` raised on every
`Appendix X to Subpart Y of Part Z` identifier. Subpart C's appendices carry the OASDI
computation tables (average wage index series, PIA benefit formulas, the old-law benefit
table, year-of-coverage earnings, special minimum PIA, automatic increase percentages,
old-law contribution and benefit base); subpart P's are the Listing of Impairments and
the medical-vocational guidelines.

## Route

The adapter now takes subpart appendices (`docs/ecfr-appendix-ingestion.md`), the
"extend the adapter" route of the #826 note, rather than an official document from the
eCFR renderer API (PR #718's route for the part 416 subpart K appendix). The adapter
keeps the appendices in the part's own hierarchy (children of their subpart rows),
reads the same retained XML as the sections, and also unblocks part 416.

| eCFR identifier | Citation path | Ordinal |
| --- | --- | ---: |
| Appendix to Subpart B of Part 404 | `us/regulation/20/404/subpart-B/appendix` | 1,000,000 |
| Appendixes to Subpart C of Part 404 (Note) | `us/regulation/20/404/subpart-C/appendixes` | 1,000,000 |
| Appendix I to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-i` | 1,000,001 |
| Appendix II to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-ii` | 1,000,002 |
| Appendix III to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-iii` | 1,000,003 |
| Appendix IV to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-iv` | 1,000,004 |
| Appendix V to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-v` | 1,000,005 |
| Appendix VI to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-vi` | 1,000,006 |
| Appendix VII to Subpart C of Part 404 | `us/regulation/20/404/subpart-C/appendix-vii` | 1,000,007 |
| Appendix 1 to Subpart P of Part 404 | `us/regulation/20/404/subpart-P/appendix-1` | 1,000,001 |
| Appendix 2 to Subpart P of Part 404 | `us/regulation/20/404/subpart-P/appendix-2` | 1,000,002 |

`I` and `V` read as roman numerals here because subpart C's other designators are
multi-character numerals (`II`, `III`, ...); appendices sort after their subpart's
sections.

## Why a whole-part scope

Release validation requires every row's parent in the same scope
(`release_quality._validate_record`: a parent found only in another scope is
`missing_parent_citation`, because Supabase derives versioned parent ids), and a profiled
release rejects a citation path carried by two scopes (`duplicate_release_citation`). An
appendix-only scope would need the part and subpart B, C and P rows, which #826's scope
already carries. So the appendices ship in a whole-part scope that **replaces**
`us/regulation/2026-10-12-title-20-part-404` in a release; a release must not carry both.

The replacement is exact for everything #826 has: the same eCFR point in time
(2026-10-08), byte-identical sources (`title-20-part-404.xml` sha256
`bdf2ce217abc258f999d54f6df1e2c7f6fa7d22ff10b8d0a3b3fc5b086b2fc50`, `title-20.structure.json`
sha256 `912fc4243129815b9a1d639fcde6885163a8c43f1d7ae8ce5d186e0e41f5d6cc`), and all 810
of its rows identical, in the same order, except `version` and the run id inside
`source_path`. Citation paths and provision ids (path-derived) are the same, so a
register entry or RuleSpec citation of a part 404 section resolves to the same text.

## Scope

| jurisdiction | class | version | units | rows | sources | coverage |
| --- | --- | --- | ---: | ---: | --- | --- |
| us | regulation | `2026-10-12-with-appendices-title-20-part-404` | 788 sections, 11 appendices | 821 | 5 files, 7.7 MB | complete, 821/821 |

```bash
axiom-corpus-ingest inventory-ecfr --base data/corpus --version 2026-10-12-with-appendices \
  --as-of 2026-10-08 --only-title 20 --only-part 404 --include-appendices
axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-10-12-with-appendices \
  --as-of 2026-10-08 --expression-date 2026-10-08 --only-title 20 --only-part 404 \
  --include-appendices
```

- Publisher: eCFR Versioner API only, captured live (no local replay). `titles.json` on
  2026-10-12 at 18:31 UTC: title 20 `latest_amended_on` 2026-09-30, `up_to_date_as_of`
  2026-10-08, so `--as-of 2026-10-08 --expression-date 2026-10-08`, as #826.
- Images: the Listing of Impairments has 3 figures (`er28mr13.002`, `er20no06.000`,
  `er28mr13.003`). Extraction archives the Federal Register's PNGs
  (`img.federalregister.gov/<id>/<id>_original_size.png`, HTTP 200, 52,215, 103,694 and
  49,988 bytes) under `ecfr/graphics/` and the body cites each as
  `[Official source image: ecfr/graphics/<ID>.png]`. They are not transcribed.
- Sources (`sources/us/regulation/2026-10-12-with-appendices-title-20-part-404/ecfr/`):
  `title-20-part-404.xml` 3,528,997 bytes sha256 `bdf2ce21…b086b2fc50`,
  `title-20.structure.json` 3,980,577 bytes sha256 `912fc424…e41f5d6cc` (both byte-identical
  to #826's), `graphics/ER28MR13.002.png` sha256 `e3ed17f1…db81252`,
  `graphics/ER20NO06.000.png` sha256 `2a0dbb40…a95c7dc`, `graphics/ER28MR13.003.png` sha256
  `d193409f…85ca7c3`.
- Timing: `inventory-ecfr` 13 s, `extract-ecfr` 18 s (host load average above 100).

## Text kept

Measured per appendix: the words of the XML (HEAD, CITA and XREF excluded, `<br/>` and
block boundaries read as breaks, inline markup joined) against the words of the row body.

| Citation path | Body characters | Source words | Words kept | Images |
| --- | ---: | ---: | ---: | ---: |
| `.../subpart-B/appendix` | 504 | 88 | 88 | 0 |
| `.../subpart-C/appendixes` | 2,685 | 457 | 457 | 0 |
| `.../subpart-C/appendix-i` | 863 | 192 | 192 | 0 |
| `.../subpart-C/appendix-ii` | 1,611 | 316 | 316 | 0 |
| `.../subpart-C/appendix-iii` | 19,754 | 4,390 | 4,390 | 0 |
| `.../subpart-C/appendix-iv` | 1,342 | 258 | 258 | 0 |
| `.../subpart-C/appendix-v` | 7,193 | 1,579 | 1,579 | 0 |
| `.../subpart-C/appendix-vi` | 194 | 56 | 56 | 0 |
| `.../subpart-C/appendix-vii` | 504 | 93 | 93 | 0 |
| `.../subpart-P/appendix-1` | 964,018 | 154,047 | 154,047 | 3 |
| `.../subpart-P/appendix-2` | 30,031 | 4,590 | 4,590 | 0 |

All 166,066 words are kept (`...` is `us/regulation/20/404`).

- Table captions are kept, as a block before the table rows (`Benefit Formulas`,
  `Table No. 1—Residual Functional Capacity: Maximum Sustained Work Capability Limited to
  Sedentary Work as a Result of Severe Medically Determinable Impairment(s)`). Before
  this change the appendix renderer dropped all 44 captions in these appendices.
- `<br/>` and adjacent paragraphs separate words: the Listing's table headings read
  `means less`, `less than or equal to`, `Table IV-A [Applicable at test sites less than
  3,000 feet above sea level]` (previously `meansless`, `thanor`, `IV-A[Applicable`).
- Not kept: the two eCFR editorial cross-references at the top of the Listing ("Link to an
  amendment published at 91 FR 40836, July 2, 2026." and "Link to a correction published
  at 91 FR 58593, Sept. 16, 2026."), which are eCFR navigation, not regulation text, and
  each appendix's bracketed source note (CITA), as for sections. The Listing's editorial
  note and effective-date note (90 FR 5590, provisions "effective until May 11, 2029")
  are kept.
- One row per appendix: the Listing of Impairments is one 964,000-character row. The
  adapter's appendix model has no sub-appendix segmentation; a listing such as 12.05 is
  reachable inside the row, not at its own path.
- Appendix bodies read only the appendix's own text; the part 404 sections are #826's
  rows, unchanged (the section renderer still drops the 4 table captions and joins the
  words at the 2 `<br/>` inside part 404 sections; a follow-up covers sections).

## Adapter change and impact

`src/axiom_corpus/corpus/ecfr.py`; tests in `tests/test_corpus_ecfr_subpart_appendices.py`
(identifier table, exhaustive roman round trip 1 to 3,999, Hypothesis properties for
designator order, a structure-versus-XML differential for placeholders, fail-closed
cases) and updated `tests/test_corpus_ecfr.py`, `tests/test_recover_ingest.py`.

- Supported: `Appendix <d> to Subpart <S> of Part <P>` with a number, a single letter or an
  uppercase roman numeral; `Appendix to Subpart ...`; `Appendixes to Subpart ...`.
  The 49 eCFR title structures of 2026-10-12 (title 35 is reserved) hold 3,918
  nonreserved appendix nodes: 1,588 part appendices the adapter already took, 579
  subpart appendices it now takes, 5 subpart appendices that fail validation (10 CFR 51
  appendices A and C and 29 CFR 2520 appendices A and B sit outside the subpart they
  name, as a part appendix naming another part does; 10 CFR 430 subpart B appendix CC
  sits beside appendix A, so CC has no order), and 1,746 other shapes that stay
  unsupported.
- Unchanged: part appendices (single letter or number), section rendering, defaults.
  Still unsupported: part appendices with roman (`Appendix II to Part 200`) or no
  designator (`Appendix to Part 720`), hyphenated or alphanumeric designators.
- Differential run (origin/main adapter against this branch, both fed the same bytes)
  over every locked eCFR XML: 49 files in 45 `us/regulation` scopes (44 `ecfr/title-*.xml`
  and 5 `official-documents/ecfrtitle-*.xml` recovery sources; 37 with a structure file).
  With appendices off, 37/37 inventories and 49/49 record sets are identical. With
  appendices on, they are identical except: the two part 416 sources
  (`2026-07-23-…` and `2026-09-11-title-20-part-416`), where main raised on
  `Appendix to Subpart K of Part 416` and the branch takes it (623 inventory items); and
  2 CFR 200 (`2026-09-24-nsf-slice-title-2-part-200`), which raises the same message in
  both, now as `EcfrAppendixError`. The caption and word-break changes reach no locked
  row: the only locked appendices (7 CFR 277 appendix A, 45 CFR 96 appendix A) have
  neither. Script and report: `~/reviews/axiom-corpus-cfr-404-appendices-2026-10-12/`
  (`differential.py`, `differential-report-v3.json`).
- Fail closed before writes: an opted-in appendix that names another part or subpart, or
  has an ambiguous designator, raises `EcfrAppendixError` (CLI exit 2) whether the
  structure or only the XML shows it, and `extract-ecfr` then writes nothing.
- Recovery scripts still refuse appendix replay, subpart appendix citations included.

## Citation-path ratchets

Measured with `scripts/validate_citation_paths.py --update-baselines` over every locked
provisions file on `main` (2,330 scopes, all present, hash-verified; `main` alone measures
exactly at the existing baselines) plus the new file: `uppercase_segments` +32, from
18,796 to 18,828; the other families are unchanged. The 32 are the paths with a
`subpart-<X>` segment: the 21 subpart containers (`subpart-A` to `subpart-V`, L reserved)
and the 11 appendices. #826 raises the same family by its 21 subpart containers, which
are the same paths, so with both merged the live count is still 18,828; if #826 lands
first, the merged baseline is `block_n` from #826 and `uppercase_segments` 18,828.

## Part 416

The same adapter change takes `Appendix to Subpart K of Part 416` at
`us/regulation/20/416/subpart-K/appendix`, the path PR #718's renderer-API manifest
(`manifests/us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml`, never locked) chose.
Taking it into the corpus means a successor of the released
`us/regulation/2026-09-11-title-20-part-416` scope, at a newer point in time; that is
left to a follow-up so this PR changes no released 416 text.

## Not done here

Cutting, publishing and activating a release that carries this scope in place of
`us/regulation/2026-10-12-title-20-part-404`, and re-pinning rulespec-us, belong to the
release owner.
