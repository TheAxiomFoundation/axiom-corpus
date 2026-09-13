# Federal statute layer: U.S. Code gaps from the needs-closure check (2026-09-13)

Closes the federal STATUTE gaps that `docs/coverage/needs-closure-2026-09-11/` found, from the
official U.S. Code (Office of the Law Revision Counsel, uscode.house.gov, USLM XML), with the
`extract-usc` adapter the repository already uses for every `us/statute` scope. One self-contained
scope per program; every extraction pointed at `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`
from the sparse worktree `~/axiom-corpus-worktrees/federal-statute` (branch
`discovery/ingest-federal-statute`, cut from `origin/main` at `8dc61300`). Everything under
`data/corpus` is local and unsigned; nothing under it is committed on this branch. GitNexus MCP
tools were not available in this session; no adapter code was changed, and the two new scripts have
no callers, so the impact analysis CLAUDE.md asks for reduces to the grep-by-hand recorded below.

| Program | Scope (`us/statute`) | Sections | Rows | Extract s | Closure elements closed |
| --- | --- | ---: | ---: | ---: | --- |
| WIC | `2026-09-13-wic-statute-1786-title-42` | 1 | 622 | 51 | `wic_usc_1786_a` to `wic_usc_1786_s` (19) |
| TANF | `2026-09-13-tanf-statute-part-a-title-42` | 23 | 1,101 | 71 | `tanf-f-usc-601` to `tanf-f-usc-619` incl. `tanf-f-usc-611a` (20) |
| CCDF | `2026-09-13-ccdf-statute-ccdbg-title-42` | 20 | 543 | 48 | `ccdf-f-usc-1` to `ccdf-f-usc-7` (7) |
| SSI | `2026-09-13-ssi-statute-1381a-1383f-title-42` | 8 | 475 | 38 | `SSI-F-USC-1381a`, `SSI-F-USC-1383` to `SSI-F-USC-1383f` (8) |
| LIHEAP | `2026-09-13-liheap-statute-chapter-94-title-42` | 13 | 269 | 44 | `LIHEAP-F-USC-8621` to `LIHEAP-F-USC-8630` (10) |
| Medicare | `2026-09-13-medicare-statute-eligibility-premiums-title-42` | 21 | 2,335 | 43 | `MED-F-USC-426-1`, `MED-F-USC-1395c` to `MED-F-USC-1395w-114`, `MED-F-USC-1396u-3` (21) |
| Medicaid | `2026-09-13-medicaid-statute-closure-title-42` | 10 + 13 subsections | 824 | 39 | the 15 `M-ST-*` EXTRACTABLE rows (list below) |
| Tax | `2026-09-13-tax-statute-closure-31-title-26` | 42 | 4,299 | 18 | the 31 `F*` EXTRACTABLE rows (list below) |
| **Total** | 8 scopes | 138 + 13 | **10,468** | 352 | 131 elements |

Every scope: coverage complete (source rows = provision rows, 0 missing, 0 extra, 0 duplicate
citations), every row has a body or a heading, no citation path is carried by any scope of the
follow-up draft selector, and the draft selector with all eight added validates `ok: true`, 0
errors (see "Release validation"). SNAP needed nothing: all 81 federal statute elements of
`snap-schema.yaml` are PRESENT, and 7 U.S.C. 2011 to 2036d (34 sections) are held whole by the
released `us/statute/2026-07-22-rulespec-title-7-consolidated`.

## Source

Publisher: uscode.house.gov only (OLRC), the same primary publisher as every held `us/statute`
scope. No Cornell LII, GovInfo republication or archived copy was consulted. The download page
(`https://uscode.house.gov/download/download.shtml`, read 2026-09-13) lists the current release
point as **Public Law 119-103 (09/02/2026)**; both titles' USLM XML carries
`docPublicationName Online@119-103` and `dcterms:created 2026-09-09`.

| Title | Zip (retained under `sources/us/statute/<scope>/olrc/`) | Zip bytes | Zip SHA-256 | Member | Member bytes | Member SHA-256 |
| --- | --- | ---: | --- | --- | ---: | --- |
| 42 | `https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc42@119-103.zip` | 18,161,900 | `28eaf3479573ea9342c208a3cd28a48aedb57dd87a30c2f978b59d1cf4757388` | `usc42.xml` | 113,735,961 | `70f0b76581baf998f5d7ff6d1e798f3e95772db4509628c5033c79d56a9f358b` |
| 26 | `https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc26@119-103.zip` | 8,290,374 | `285b9862808f26055c3eed16c2aca1d8de1fae96b581f44a55cfedb907a46eff` | `usc26.xml` | 55,871,474 | `ab999da948658a2265f762abfedd72413a3f7828d34659ff27ed8240fcd956e4` |

Each scope retains the publisher's zip byte-for-byte under `olrc/` and the unzipped member under
`uslm/usc<title>.xml` (the layout of the 2026-07-24 and 2026-07-27 Title 26 scopes); the member was
`cmp`-checked against the downloaded zip before extraction, and `extract-usc` retains it raw (no
reserialized excerpt). `--source-as-of 2026-09-02 --expression-date 2026-09-02` is the release
point's currency date, the convention of the 2026-07-24 repair ("current through PL 119-102 as of
2026-07-12"); the XML creation date 2026-09-09 is in every row's `metadata.created_date`.

## Version strings

`extract-usc` always appends `-title-<n>` to `--version` (`usc_run_id`; SNAP precedent
`2026-07-21-snap-chapter-51-title-7-title-7`), so the requested pattern
`2026-09-13-<program>-statute-<title>-<qualifier>` comes out as
`2026-09-13-<program>-statute-<qualifier>-title-<n>`. All four parts are present; only the order is
the adapter's.

## Self-containment: why the scopes carry no title row

The released consolidated scopes already carry the title rows `us/statute/42`
(`2026-07-19-rulespec-title-42-consolidated`) and `us/statute/26`
(`2026-08-03-rulespec-title-26-current-union`), and a release selector cannot carry a citation path
twice (`duplicate_release_citation` is an error). `extract-usc --section` without `--include-title`
emits section rows whose `parent_citation_path` is the absent title row, and release validation
checks parent integrity scope-locally (`missing_parent_citation` is an error: Supabase derives
versioned parent UUIDs, so a parent in another scope cannot satisfy the FK). The released
`-r2026-07-15-self-contained` statute scopes resolve this by carrying section rows with no parent
link (their inventories still record the title as `metadata.parent_citation_path`), and
`scripts/repair_us_release_source_references.py` set the precedent of removing, not fabricating,
parent links that do not resolve. The new `scripts/self_contain_usc_scope.py` applies exactly that
after each extraction: for every row whose parent is not in the scope it clears
`parent_citation_path`/`parent_id`, records `metadata.self_contained_root: true` and
`metadata.detached_parent_citation_path: <parent>`, and rewrites the coverage report (fail-closed if
coverage is not complete). Unit test: `tests/test_self_contain_usc_scope.py`. Detached roots per
scope equal the section count, except Medicaid (below).

## Collisions found and how they were resolved

Before extracting, every citation path of the 21 `us/statute` scopes in
`docs/ingest-runs/2026-09-13-us-rulespec-followup-union.selector.json` (10,013 paths; read from the
main checkout on `release/2026-09-13-followup`) was listed. Held Title 42 sections: 402-416, 426,
1381-1382j, 1396a (partial), 1396b (partial), 1396d (partial), 1396p (partial), 1396u-1, 1397aa-mm,
housing sections, 18795-18795a. Held Title 26: 117 sections (1, 2, 21-26, 27, 30D, 32, 36B, 42,
45A, 55-59, 61-65, 67, 68, 85, 86, 102, 104, 112, 151, 152, 163-165, 170, 172, 199A, 212-225, 408,
443, 901-904, 911, 931, 933, 1211-1222, 1401-1411, 3101-3512, 6012, 6013, 6401, 7701, 7703).

- **No new section collides.** Every WIC, TANF, CCDF, SSI, LIHEAP, Medicare and tax section is
  absent from the selection, so those scopes are whole-section extractions with no consolidation.
- **Medicaid, 1396a / 1396d / 1396p.** The released
  `2026-06-26-medicaid-title-42-...-r2026-07-17-dedup` scope holds subsections 1396a(a)(10), (e),
  (f), (l), (m); 1396b(f), (v); 1396d(a), (n), (p), (q); 1396p(f), and the PL 119-21 scope holds
  1396a(xx), each without a section row or a `1396a/a` container (they are themselves self-contained
  roots). The needed elements are sibling subsections, so the closure scope takes them by exact
  `--citation-path` (1396a(a)(3), (a)(17), (a)(25), (a)(34), (a)(47), (k), (r); 1396d(b), (y), (z);
  1396p(b), (c), (d)) with their descendants, and `self_contain_usc_scope.py` detaches their
  parents (`1396a/a`, `1396a`, `1396d`, `1396p`), the same shape the released scope already has. No
  released row is duplicated and no consolidation was needed; the released Medicaid scopes stay
  selected untouched. Re-extracting whole 1396a/1396d/1396p and consolidating with
  `scripts/consolidate_release_scopes.py` was rejected because it would swap a released scope and
  need a text carrier for every subsection whose wording moved between release points 119-59 and
  119-103; the one-scope-per-family successor can still be built later from these two scopes.
- **SSI, Medicare 426.** 1381, 1382-1382j and 426 stay in their released scopes; the new scopes take
  only 1381a, 1383-1383f and 426-1.
- **Dashed section numbers.** USLM identifiers use an en dash (`1395i–2`, `1396o–1`, `1320b–7`), and
  so do the held citation paths (`us/statute/42/1396u–1`). `--section` rejects non-ASCII, so those
  sections were passed as `--citation-path us/statute/42/1395i–2` etc.

## Per program

### WIC (`wic.md`, `wic-schema.yaml`)
42 U.S.C. 1786, 622 rows (1 section, 19 subsections (a)-(s), 127 paragraphs, 194 subparagraphs,
176 clauses, 86 subclauses, 17 items, 2 subitems). Closes `wic_usc_1786_a` to `wic_usc_1786_s`; each
subsection is its own row (`us/statute/42/1786/d` etc.). Nothing missing.

### TANF (`tanf.md`, `tanf-schema.yaml`)
Every section of 42 U.S.C. chapter 7 subchapter IV part A: 601, 602, 603, 603a (transferred,
heading-only row), 604, 604a, 605, 606, 607, 608, 608a, 609, 610, 611, 611a, 612, 613, 614
(repealed, heading-only row), 615, 616, 617, 618, 619; 1,101 rows. Closes `tanf-f-usc-601` to
`tanf-f-usc-619` and `tanf-f-usc-611a` (20; 603a, 604a and 608a are taken for completeness of the
part). Nothing missing.

### CCDF (`ccdf.md`, `ccdf-schema.yaml`)
Every section of chapter 105 subchapter II-B (CCDBG Act 658A-658T): 9857, 9858, 9858a-9858r; 543
rows. `ccdf-f-usc-1` names "9857-9857a"; 9857a is not a distinct USLM section (the Act's goals are
9857(b), `us/statute/42/9857/b`), so the element is closed by 9857. Closes `ccdf-f-usc-1` to
`ccdf-f-usc-7`. Nothing missing.

### SSI (`ssi.md`, `ssi-schema.yaml`)
1381a, 1383, 1383a, 1383b, 1383c, 1383d, 1383e, 1383f; 475 rows (1383 alone is 97 KB of body, 
representative payees, overpayments, redeterminations). Closes `SSI-F-USC-1381a`, `SSI-F-USC-1383`
to `SSI-F-USC-1383f`. Nothing missing.

### LIHEAP (`liheap.md`, `liheap-schema.yaml`)
Every section of chapter 94 subchapter II: 8621-8630 including 8626a, 8626b, 8628a; 269 rows.
Closes `LIHEAP-F-USC-8621` to `LIHEAP-F-USC-8630`. Nothing missing.

### Medicare (`medicare.md`, `medicare-schema.yaml`)
426-1, 1395c, 1395d, 1395e, 1395i-2, 1395i-2a, 1395k, 1395l, 1395o, 1395p, 1395q, 1395r, 1395s,
1395v, 1395w-21, 1395w-22, 1395w-101, 1395w-102, 1395w-113, 1395w-114, 1396u-3; 2,335 rows (1395l
alone 212 KB). Closes `MED-F-USC-426-1`, `MED-F-USC-1395c` to `MED-F-USC-1395w-114` and
`MED-F-USC-1396u-3` (21; the schema's 23 statute rows minus `MED-F-USC-1396a` and
`MED-F-USC-1396d`, which the report already counts PRESENT from the released Medicaid scope).
Observation, not in the work order: `MED-F-USC-1396d` names 1396d(s) (QDWI) but the released scope
holds 1396d(a), (n), (p), (q) only; 1396d(s) is not in any scope.

### Medicaid (`medicaid.md`, `medicaid-schema.yaml`)
Whole sections 1315, 1320b-7, 1396o, 1396o-1, 1396r-1, 1396r-1a, 1396r-1b, 1396r-1c, 1396r-5,
1396r-6 and subsections 1396a(a)(3), (a)(17), (a)(25), (a)(34), (a)(47), (k), (r); 1396d(b), (y),
(z); 1396p(b), (c), (d); 824 rows, 23 self-contained roots. Closes `M-ST-1396a-a17` (with
1396a(r)(2) via `us/statute/42/1396a/r/2`), `M-ST-1396a-a34`, `M-ST-1396a-a47` (with 1396r-1 to
1396r-1c), `M-ST-1396a-k`, `M-ST-1396d-b-y`, `M-ST-1396o` (with 1396o-1), `M-ST-1396p-b`,
`M-ST-1396p-c`, `M-ST-1396p-d`, `M-ST-1396r-5`, `M-ST-1396r-6`, `M-ST-1320b-7`, `M-ST-1315`,
`M-ST-1396a-a3`, `M-ST-1396a-a25` (15). Nothing missing on the statute side; the CFR halves of
several of these elements (42 CFR 435.915, 435.119, 447.50-447.57, 435.940-435.965, 431.200-431.250,
433 subpart D, 435.610) belong to the eCFR agent.

### Tax (`tax.md`, `tax-schema.yaml`)
26 U.S.C. 3, 23, 25, 31, 35, 53, 66, 71 (repealed, heading-only), 72, 101, 103, 108, 117, 121,
125, 129, 132, 135, 137, 139, 162, 215 (repealed, heading-only), 217, 401, 402, 403, 415, 457,
461, 469, 529, 529A, 530, 1001, 1012, 1014, 1015, 1016, 1250, 6072, 6081, 6654; 4,299 rows.
Closes `F007`, `F012`, `F024`, `F035`, `F036`, `F037`, `F052`, `F053`, `F056`, `F058`, `F060`,
`F062`, `F063`, `F064`, `F065`, `F066`, `F067`, `F068`, `F069`, `F072`, `F083`, `F092`, `F094`,
`F095`, `F096`, `F097`, `F098`, `F101`, `F102`, `F113`, `F114` (31). `F098` names 1011-1016; 1011
and 1013 were not in the report's section list and were not taken (1011 general basis rule, 1013
inventory basis); everything the report named is present. `F101` also names 1(h)(6), held in the
released recovery scope.

## Commands

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
# per scope: retain the publisher zip and its member inside the scope's source tree, then extract
V=2026-09-13-wic-statute-1786; T=42; RUN_ID=$V-title-$T; SRC=$B/sources/us/statute/$RUN_ID
mkdir -p $SRC/olrc $SRC/uslm && cp xml_usc$T@119-103.zip $SRC/olrc/ && unzip -q $SRC/olrc/xml_usc$T@119-103.zip -d $SRC/uslm
uv run axiom-corpus-ingest extract-usc --base $B --version $V --source-xml $SRC/uslm/usc$T.xml --title $T \
  --source-as-of 2026-09-02 --expression-date 2026-09-02 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc$T@119-103.zip \
  --section 1786
uv run python scripts/self_contain_usc_scope.py --base $B --version $RUN_ID
```

Section filters per scope (`P=us/statute/42`): TANF `--section 601 602 603 603a 604 604a 605 606
607 608 608a 609 610 611 611a 612 613 614 615 616 617 618 619`; CCDF `--section 9857 9858 9858a
... 9858r`; SSI `--section 1381a 1383 1383a 1383b 1383c 1383d 1383e 1383f`; LIHEAP `--section 8621
8622 8623 8624 8625 8626 8626a 8626b 8627 8628 8628a 8629 8630`; Medicare `--citation-path $P/426–1
--section 1395c 1395d 1395e --citation-path $P/1395i–2 $P/1395i–2a --section 1395k 1395l 1395o
1395p 1395q 1395r 1395s 1395v --citation-path $P/1395w–21 $P/1395w–22 $P/1395w–101 $P/1395w–102
$P/1395w–113 $P/1395w–114 $P/1396u–3`; Medicaid `--section 1315 1396o --citation-path $P/1320b–7
$P/1396o–1 $P/1396r–1 $P/1396r–1a $P/1396r–1b $P/1396r–1c $P/1396r–5 $P/1396r–6 $P/1396a/a/3
$P/1396a/a/17 $P/1396a/a/25 $P/1396a/a/34 $P/1396a/a/47 $P/1396a/k $P/1396a/r $P/1396d/b $P/1396d/y
$P/1396d/z $P/1396p/b $P/1396p/c $P/1396p/d`; tax (title 26) `--section 3 23 25 31 35 53 66 71 72
101 103 108 117 121 125 129 132 135 137 139 162 215 217 401 402 403 415 457 461 469 529 529A 530
1001 1012 1014 1015 1016 1250 6072 6081 6654` (each value its own `--section`/`--citation-path`).

Queue rows: `uv run python scripts/update_federal_statute_queue_rows.py --base $B`.

## Release validation

After each scope a draft selector equal to the follow-up draft plus the scopes so far was validated
from the worktree:

```bash
uv run axiom-corpus-ingest validate-release --base $B --release <draft.json> --ignore-r2-missing --max-issues 50
```

| Draft | Scopes | Result | Seconds |
| --- | ---: | --- | ---: |
| follow-up + WIC | 557 | `ok: true`, 0 errors, 546 warnings | 79 |
| follow-up + WIC, TANF, CCDF, SSI, LIHEAP | 561 | `ok: true`, 0 errors, 546 warnings | 53 |
| follow-up + all eight | 564 | `ok: true`, 0 errors, 546 warnings | 44 |

The 546 warnings are the pre-existing ones (541 `missing_parent_id` in
`us-ca/regulation/2026-07-13-recovery`, 5 `unsectioned_document_body`); none names a
`2026-09-13-*-statute-*` scope, and the count did not move, so the new scopes add no warning and no
`duplicate_release_citation`.

## Queue rows

`scripts/update_federal_statute_queue_rows.py` adds one `agent_ready` row per program queue
(`wic`, `tanf`, `ccdf`, `ssi`, `liheap`, `medicare`, `medicaid`, `tax`), inserted after the last
existing `us` row in the shape of the 2026-09-11 eCFR follow-on rows, keyed by
`source_kind: federal_statute_uscode_uslm` so a re-run refreshes instead of duplicating. Section and
row counts are read from the scope's coverage report and provisions (never typed), and
`status_counts` is recomputed the way the builder scripts do; the files round-trip through
`yaml.safe_dump(sort_keys=False, allow_unicode=True, width=120)` and the diffs are the new row plus
the count line only. SNAP has no agent queue file and needed no row.

## Checks

- `uv run ruff check scripts`: passes; `ruff format` applied to the two new scripts and the test.
- `uv run pytest -q tests/test_self_contain_usc_scope.py`: 2 passed.
- Focused selection in the sparse worktree (`-m "not integration and not slow" -k "manifest or
  official_documents or discovery or usc or self_contain"`): 341 passed, 2 skipped, 20 failed in 49 s. Every failure opens a retained `data/corpus` artifact the sparse worktree does not have (`FileNotFoundError` on `data/corpus/...`, `KeyError` on a path read from a missing provisions file, `missing_inventory` in the BE promotion validate, "Israel source directory does not exist"): the ten the gotchas note lists (BE rulespec promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manuals) plus the ten the wider `usc` keyword pulls in (`test_corpus_usc` official Title 26 x2, `test_us_usc_amt_ftc_sections` x2, `test_recover_ingest` uscode-olrc-xml x2, `test_us_release_immutable_scope_successors`, `test_sc_act110_successor`, `test_armenia_arlis`, `test_israel_openlaw`). Not re-run in the main checkout, which was left untouched.
- Disk: 20 GB free at start, 7.3 GB after the eight scopes (other agents' worktrees consumed most of
  the difference; the eight scopes hold 943 MB of sources, 7 x 126 MB Title 42 and 61 MB Title 26).

## Controller

Selector additions (no swaps; no released scope superseded; no unreleased scope dropped):

```json
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-wic-statute-1786-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-tanf-statute-part-a-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-ccdf-statute-ccdbg-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-ssi-statute-1381a-1383f-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-liheap-statute-chapter-94-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-medicare-statute-eligibility-premiums-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-medicaid-statute-closure-title-42"},
{"document_class": "statute", "jurisdiction": "us", "version": "2026-09-13-tax-statute-closure-31-title-26"}
```

Decisions needed before signing:

1. **Retained Title 42 XML is 113.7 MB per scope, above GitHub's 100 MB hard limit.** Since the
   2026-07-26 change (`a0978c30`) canonical `extract-usc` retains the raw source bytes, and the only
   scopes cut under that rule were Title 26 (55.9 MB). Seven Title 42 scopes here each retain
   `uslm/usc42.xml` (113,735,961 bytes) plus the 18 MB publisher zip; `sign_release_scopes.sh`
   would try to commit 7 x 132 MB and the push would be rejected for the XML. Options: (a) an
   `extract-usc --source-zip` variant that retains the publisher zip as the inventory source
   (sha256 of the zip; the recovery tooling already verifies single-member USLM archives) and parses
   the member in memory, then re-run the eight extractions (about 6 minutes; the zips are already in
   place under `olrc/`); (b) Git LFS for `data/corpus/sources/us/statute/*/uslm/usc42.xml`; (c) one
   Title 42 scope for all seven programs (still one 113.7 MB file, so it does not help alone). The
   pre-2026-07-26 derived excerpt (`_source_artifact_bytes`, still in `usc.py` with a test) is the
   shape of every released Title 42 scope but is a reserialization and was deprecated on purpose.
   Both the zip and the raw member are retained so any option can be taken without re-downloading.
2. Version-string order (`...-<qualifier>-title-<n>`) is the adapter's; rename only if the pattern
   matters downstream.
3. Optional follow-ups outside the work order: 42 U.S.C. 1396d(s) (QDWI definition) is in no scope;
   26 U.S.C. 1011 and 1013 (basis) were not named by the tax report and were not taken.
