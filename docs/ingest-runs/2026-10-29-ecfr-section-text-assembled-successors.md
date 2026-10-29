# eCFR section-text successors for assembled federal scopes

This run prepares two immutable successor scopes after #832 merged at
`b92bd3033c0bed9c1b7ce9a1b37ff3d9476f69fb`. The eCFR renderer now keeps table
captions as `[Table caption: …]` blocks and separates words across `<br/>`.
The predecessor locks continue to pin their original bytes. These successors
carry the rendering fix while preserving each predecessor's assembly decisions.

| Key | Predecessor version | Successor version |
| --- | --- | --- |
| `recovery` | `2026-07-13-recovery-r2026-07-17-dedup` | `2026-07-13-recovery-r2026-07-17-dedup-r2026-10-29-ecfr-section-text` |
| `26-1` | `2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated` | `2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated-r2026-10-29-ecfr-section-text` |

Both scopes use jurisdiction `us` and document class `regulation`. This PR
signs and locks both successors and adds recovery's content-baseline entry. It
changes no predecessor lock, release selector, ratchet, RuleSpec module or
serving database.

Five other scopes that a native `extract-ecfr` run reproduces get their
successors in a separate PR, as does 20 CFR part 416 (#830).

## Reproducer and guards

The tracked command is
[`scripts/repro/ecfr_section_text_successors.py`](../../scripts/repro/ecfr_section_text_successors.py).
It reads the fetched predecessor from this checkout's `data/corpus`, writes
the successor there and refuses any existing successor artifact. The raw
mapping approach follows
[`scripts/repair_local_file_download_urls.py`](../../scripts/repair_local_file_download_urls.py):
preserve every field the locked rows contain, then permit only the explicitly
reviewed changes.

For recovery, the reproducer compares the locked body with both renderers.
It obtains the pre-#832 source through
`git show de81c43afd87bacb828b193a59e98b0439561e50:src/axiom_corpus/corpus/ecfr.py`
and requires source SHA-256
`5439c5a61e2646be10f8a1c26b4423d370088a9fbcb9ca411090373ebb250fe2`.
It fails if git cannot supply that commit or the hash differs. It parses the
source with Python's AST and evaluates exactly `_section_body`, `_table_text`
and `_element_text_with_breaks` in the current eCFR module namespace.

The reproducer checks each predecessor file's locked size and SHA-256 before
use. It requires unique provision citations, matching inventory citations,
matching inventory/provision source paths and inventory hashes that agree with
the lock. Each section must resolve exactly once in its own retained XML, with
the same heading and consistent dates within that source's selected rows.
Recovery must have exactly the two assigned pre-/post-#832 deltas and exactly
the 14 inherited differences listed below; every changed locked body must equal
the pre-#832 rendering. The `26-1` recipe renders each section from its own
locked XML with the current renderer and must change exactly its 21 assigned
bodies.

Both recipes require the final changed-body set to equal the assigned set and
reject paragraph rows that name a changed section as their parent or have a
citation beneath one. They preserve row order,
citations, parent citation paths, publisher URLs, source dates, metadata and
structure-only placeholders. They map the scope version and source prefix,
including nested image references. They map an `id` or `parent_id` only when it
equals `deterministic_provision_id(citation_path, predecessor_version)`;
path-only identifiers keep their values, and unknown identity schemes fail.
The reproducer copies only locked source names, hashes the copies and reports
same-scope parent residuals. It carries the locked coverage report with its
version mapped; the release gate recomputes coverage from the successor
inventory and provisions. It prints a JSON report (and writes it to `--report`
when given).

Current local eCFR XML replay constructs official reader URLs. The historical
`file:` download-URL bug described by
[`scripts/repair_local_file_download_urls.py`](../../scripts/repair_local_file_download_urls.py)
does not justify replacing these scopes' locked HTTPS provenance. The
reproducer carries their recorded URLs unchanged. Neither assembled scope
retains a structure JSON response, so this run makes no claim about historic
structure-response byte identity.

## Recovery assembly and command

The predecessor has 1,073 rows: 254 sections, 22 subparts, 2 parts, 380 inferred
paragraphs, 412 generic blocks and 3 generic documents. The July recovery batch
combined five eCFR part XML snapshots with generic official-document captures.
[`scripts/recover_ingest_batch.py`](../../scripts/recover_ingest_batch.py)
contains the assembly: its eCFR branch calls the canonical parser with the
recovery date and appends requested inferred paragraph records; its generic
branch handles the HTML captures. Its batch inputs, report and corpus paths
belong to the original recovery run, so invoking the batch again would not
reproduce this successor alone.

The lineage also carries the dedup decisions from #358, #360 and #365. #358
retained the original canonical carriers and removed ambiguous recovery
duplicates; #360 rebuilt inventory and coverage; #365 introduced the
`-r2026-07-17-dedup` keys after a release had frozen the original versions.
The retained manifests record that history at
`.axiom/ingest-manifests/us/regulation/2026-07-13-recovery.json` and
`.axiom/ingest-manifests/us/regulation/2026-07-13-recovery-r2026-07-17-dedup.json`.
[`scripts/deduplicate_release_selector.py`](../../scripts/deduplicate_release_selector.py)
selects the canonical carrier, refuses ambiguous ownership and rejects parent
removals that would orphan retained rows. A whole-part extraction would discard
the generic/paragraph mix and reintroduce citations that those decisions
removed.

The five XML sidecars request `2026-07-01`; the corresponding rows retain
`source_as_of` and `expression_date` of `2026-07-13`, the recovery-run date.
The reproducer preserves both facts. The five inferred-paragraph frontiers are
7 CFR 246.7 and 247.9, and 42 CFR 435.601, 435.602 and 435.603. Neither changed
section has an inferred paragraph descendant, so the 380 paragraph bodies,
offsets, hashes and `provision-anchors/1.0.0` metadata remain valid unchanged.

Run these commands from the checkout root after configuring the normal corpus
fetch environment:

```bash
uv run axiom-corpus-ingest corpus fetch us/regulation/2026-07-13-recovery-r2026-07-17-dedup --workers 1
uv run python scripts/repro/ecfr_section_text_successors.py --key recovery
```

The second line is the exact portable reproduction command for signing.

| Changed citation | Rendering change | Characters, before → after |
| --- | --- | ---: |
| `us/regulation/42/457/555` | Separate `Maximum` and `Copayment` at the source break | 3,706 → 3,707 |
| `us/regulation/7/246/10` | Retain two food-package table captions and separate table-cell words at source breaks | 80,304 → 81,002 |

### Earlier extractor omissions retained for a later successor

Fourteen locked section bodies differ from both the pre-#832 renderer and the
current renderer, while those two renderers agree with each other. This run
keeps their locked bodies. Re-rendering them would mix an earlier extractor
repair into the two-body delta and mark three consumers' source evidence stale
for heading changes. The hub will review these known omissions in a later
successor round.

| Citation | What the current extractor adds | Known rulespec-us consumer |
| --- | --- | --- |
| `us/regulation/42/457/608` | `FP-1`/`FP-2` allotment formulas, variable definitions and territory percentages | — |
| `us/regulation/42/457/618` | `FP-2` ten-percent-limit formula and variable definitions | — |
| `us/regulation/42/457/628` | `FP-2` list of applicable administration, appeals and nondiscrimination regulations | — |
| `us/regulation/7/246/2` | `Editorial Note:` heading | — |
| `us/regulation/7/246/4` | `Editorial Note` heading | — |
| `us/regulation/7/246/7` | `Editorial Note:` heading | Modules cite inferred paragraphs `c` and `d` beneath this section |
| `us/regulation/7/246/16` | `Editorial Note:` heading | — |
| `us/regulation/7/247/8` | `FP` application choices `YES [ ]` and `NO [ ]` | — |
| `us/regulation/7/247/9` | `Editorial Note:` heading | Modules cite this section |
| `us/regulation/7/273/1` | `Editorial Note:` heading | — |
| `us/regulation/7/273/11` | `Editorial Note:` heading | Modules cite this section |
| `us/regulation/7/273/12` | `Editorial Note:` heading | — |
| `us/regulation/7/273/13` | `Editorial Note:` heading | — |
| `us/regulation/7/273/21` | `FP` sentence directing mass changes when a State agency uses the PA grant paid in the issuance month, plus `Editorial Note:` heading | — |

The `—` entries make no claim that no consumer exists. The three named
consumer relationships explain the requested preservation decision; this run
does not edit a rules repository.

### Recovery source hashes

Every suffix below lives under
`data/corpus/sources/us/regulation/<recovery-version>/`, with the predecessor
or successor version from the first table. The predecessor lock pins all 16
files. The successor must retain every byte and SHA-256.

| Source suffix | Bytes | SHA-256 |
| --- | ---: | --- |
| `official-documents/ecfrtitle-42-part-435.xml` | 449,436 | `f9f2683181f482e4ee699c86fac721b61d1945ef134f733f88f83c052750e910` |
| `official-documents/ecfrtitle-42-part-457.xml` | 398,330 | `f5e24a8e77a38b83e76fad7b94e9e4a0943a030d1ee08e90e376b86eb54a977e` |
| `official-documents/ecfrtitle-7-part-246.xml` | 544,372 | `e39cdedf98a30187208208bc73be5cf0554a556cd6bb0b0ad9be68312b12be44` |
| `official-documents/ecfrtitle-7-part-247.xml` | 110,946 | `8bf65858377fbcb087b16e0997d72863116656fe5ea104444cd6570d73a6d123` |
| `official-documents/ecfrtitle-7-part-273.xml` | 895,461 | `92d5f3baba66e0f7f8ba2a2887a2a664166fcc0deb275b1b143a7ca23a4114a6` |
| `official-documents/release-scope-us-regulation-2026-05-10-snap-7-cfr-273` | 1,628,162 | `8eae2d749ffb007fc304cd914f6f75022e3aa2dbbf30feb57e3744ec9a6156da` |
| `official-documents/release-scope-us-regulation-2026-06-03-cms-2454-ifc-42-cfr-435-community-engagement` | 1,277,858 | `2ef8bfb3eb99b5f5d93eb5c9b6d932e7c8adc4af3d4484f6583368920720eab9` |
| `official-documents/release-scope-us-regulation-2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments` | 1,277,858 | `eeb1393b1017b7092da6bb9d714d12bd6bad8a0b1b89f55e3ae5070fdb619af5` |
| `provenance/ecfrtitle-42-part-435.xml.json` | 255 | `96dec83d39cde4757d25554554d4c4e19059fac7d7818309e72d38d8115e051e` |
| `provenance/ecfrtitle-42-part-457.xml.json` | 255 | `cd9c4170006a8dfdb6da3a78107d8d78d6610c38eaf119bd53c6b27c604eb5b9` |
| `provenance/ecfrtitle-7-part-246.xml.json` | 253 | `b014c331c13d3f557bda8853380b394e320263aed6ea3de3639bd2246e32e57a` |
| `provenance/ecfrtitle-7-part-247.xml.json` | 253 | `665f0402dfb7700a50efdc5fa2bd2be86bef2f0d8c568faf63cdb0d3e980d96f` |
| `provenance/ecfrtitle-7-part-273.xml.json` | 253 | `6d3544e20d201cf02236df44d82f0f4504adbf9ecb6034f76e28cc3cca4f7416` |
| `provenance/release-scope-us-regulation-2026-05-10-snap-7-cfr-273.json` | 370 | `a77e8dd0309592144f109105fdb13fd19938eb3154a4d0c89c11c114fcdb9dab` |
| `provenance/release-scope-us-regulation-2026-06-03-cms-2454-ifc-42-cfr-435-community-engagement.json` | 460 | `02f1dda07551eef9ff7f07aac3a9d14cd5b215563d81b6acbb80600e70eb014d` |
| `provenance/release-scope-us-regulation-2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments.json` | 457 | `7cf1e9f1529d775b57b68fd760580659c8466aa3722124ff005f1957840bd3cd` |

## Title 26 part 1 assembly and command

The predecessor contains one part container and 373 sections. Three captures
and two ordered consolidations produced its 374 rows:

1. [`2026-07-24-usc-1401-coordination-repair.md`](2026-07-24-usc-1401-coordination-repair.md)
   records the retained `2026-07-22` XML and the two-row part/§ 1.1401-1 slice.
   [`scripts/repro/us_1401_coordination_repair.py`](../../scripts/repro/us_1401_coordination_repair.py)
   reproduces that source slice with `--source-xml` and `--section 1.1401-1`.
2. [`2026-09-13-federal-cfr-layer.md`](2026-09-13-federal-cfr-layer.md)
   records 344 further section selectors from `2026-09-10`, plus the part
   container and six formula PNGs. It also records the first consolidation:
   the original two rows first, then the 345-row capture, folding the duplicate
   bodyless part container into 346 rows.
3. [`2026-10-06-w6-federal.md`](2026-10-06-w6-federal.md) records 28 live
   § 1.414 section selectors from `2026-10-05`, plus the part container.
   [`2026-10-07-w6-release-consolidation.md`](2026-10-07-w6-release-consolidation.md)
   records the second consolidation: the prior 346 rows first, then the 29-row
   capture, folding that part container into the final 374 rows.

[`scripts/consolidate_release_scopes.py`](../../scripts/consolidate_release_scopes.py)
rewrites version-derived identities, nests each source directory under its
input version, folds structural duplicates and requires a preference for
conflicting duplicate bodies. The retained container and § 1.1401-1 keep
`2026-07-22` dates and null chapter/subchapter metadata; the 344 later sections
keep `2026-09-10` dates and chapter I/subchapter A; the final 28 keep
`2026-10-05` dates and chapter I/subchapter A. A single native part extraction
cannot recreate these source assignments, dates, ancestry and consolidation
identities. This recipe re-renders every section from its own locked XML and
preserves the assembled fields. It carries the publisher-empty § 1.163-16
placeholder and all six formula images without adding transcriptions.

```bash
uv run axiom-corpus-ingest corpus fetch us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated --workers 1
uv run python scripts/repro/ecfr_section_text_successors.py --key 26-1
```

The second line is the exact portable reproduction command for signing.

| Changed citation | Rendering change | Characters, before → after |
| --- | --- | ---: |
| `us/regulation/26/1/1016-3` | Word breaks | 24,123 → 24,124 |
| `us/regulation/26/1/1411-3` | Word breaks | 25,535 → 25,539 |
| `us/regulation/26/1/163-2` | Table captions | 9,086 → 9,226 |
| `us/regulation/26/1/163-j-2` | Table captions | 25,696 → 25,802 |
| `us/regulation/26/1/163-j-5` | Table captions | 31,037 → 31,231 |
| `us/regulation/26/1/163-j-6` | Table captions | 178,497 → 181,657 |
| `us/regulation/26/1/170A-10` | Table captions | 52,522 → 52,683 |
| `us/regulation/26/1/170A-12` | Table captions | 16,976 → 17,022 |
| `us/regulation/26/1/199A-6` | Table captions | 22,723 → 22,785 |
| `us/regulation/26/1/36B-3` | Word breaks | 45,374 → 45,376 |
| `us/regulation/26/1/36B-4` | Word breaks | 61,382 → 61,383 |
| `us/regulation/26/1/401-k-1` | Word breaks | 81,557 → 81,558 |
| `us/regulation/26/1/401-k-2` | Word breaks | 81,929 → 81,943 |
| `us/regulation/26/1/401-l-2` | Table captions | 10,586 → 10,610 |
| `us/regulation/26/1/401-l-3` | Table captions | 78,020 → 78,279 |
| `us/regulation/26/1/401-l-4` | Table captions | 14,827 → 15,394 |
| `us/regulation/26/1/401-m-2` | Word breaks | 75,003 → 75,008 |
| `us/regulation/26/1/404-a-13` | Table captions | 7,193 → 7,612 |
| `us/regulation/26/1/414-c-2` | Table captions | 11,061 → 11,124 |
| `us/regulation/26/1/414-c-4` | Table captions | 15,564 → 15,595 |
| `us/regulation/26/1/414-l-1` | Table captions | 28,616 → 28,666 |

Fourteen bodies gain captions; seven change only word separation. Every
non-caption textual difference adds whitespace only.

### Title 26 part 1 source hashes

Every suffix below lives under
`data/corpus/sources/us/regulation/<26-1-version>/`, with the predecessor or
successor version from the first table. To keep the source map readable,
`A` expands to
`2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated`,
`B` to `2026-07-24-1401-coordination-repair-title-26-part-1`, `C` to
`2026-09-13-title-26-part-1`, and `D` to
`2026-10-06-w6-federal-ecfr-closure-title-26-part-1`.
The predecessor lock pins all nine files. The successor must retain every byte
and SHA-256.

| Source suffix | Bytes | SHA-256 |
| --- | ---: | --- |
| `A/B/ecfr/title-26-part-1.xml` | 70,089,620 | `1e5ca5d86df2ebf303d2df1eb9d162412e549896118779621d41139c9662001a` |
| `A/C/ecfr/graphics/EC14NO91.175.png` | 729 | `8fcad8bc0c3062c031eb11fee1222560078fe24d3edf00202f9f82db885986c1` |
| `A/C/ecfr/graphics/ER05MY03.002.png` | 1,497 | `d7bb822e184aaa0930f2914a4ef715ac8dcc87f8c65ffdd6edae6e40031d0ee4` |
| `A/C/ecfr/graphics/ER21JY95.001.png` | 944 | `06c02fa9b57cc1a7972090a310b24b6603b8d92b52832be301bd1e44a4376dc0` |
| `A/C/ecfr/graphics/ER21JY95.002.png` | 2,705 | `cb3a4fe479e68ab15c14dd028b2153d3f78e472af7772266790360df24dbd60d` |
| `A/C/ecfr/graphics/ER21JY95.003.png` | 4,672 | `e0683fd43fadc1271f12895f45842d5aaf4c225e7c4822778ea2bb68f461c5e5` |
| `A/C/ecfr/graphics/ER21JY95.004.png` | 1,634 | `f61b850c7bd18e5ae894c991dad5808372eae7cd2536415d55489f96f2590e76` |
| `A/C/ecfr/title-26-part-1.xml` | 70,106,353 | `cbad1cf646425f85f951a0be49e2e103590cebd31e74b8f77059aa5e213ded5b` |
| `D/ecfr/title-26-part-1.xml` | 70,155,407 | `8892c839055de1cc94aa614263a3f27acf443a6622ae27d06888cb272883cf6a` |

## Row comparisons and gates

This reproducer and the research helper it came from, run on separately fetched
predecessors, produced byte-identical successors: all 31 files (recovery's 16 sources and
three derived artifacts, `26-1`'s nine sources and three derived artifacts).
Every source hash equals its predecessor lock.

| Comparison | `recovery` | `26-1` |
| --- | ---: | ---: |
| Predecessor / successor rows | 1,073 / 1,073 | 374 / 374 |
| Equal rows after the version, source-prefix and identity mapping | 1,071 | 353 |
| Changed bodies | 2 | 21 |
| Added / removed citations | 0 / 0 | 0 / 0 |
| Row order | unchanged | unchanged |
| Same-scope parent residuals | 0 | 0 |

Recovery's raw differences are `body` on two rows plus `version` and
`source_path` on every row; its path-only identifiers keep their values.
`26-1`'s raw differences are `body` on 21 rows, `version`, `source_path` and the
version-derived `id` on every row, and the version-derived `parent_id` on its 373
sections. Inventory and coverage keep their predecessor content apart from the
version and source-prefix mapping.

| Gate | `recovery` | `26-1` |
| --- | --- | --- |
| Content scan | Exactly the predecessor's nine `navigation_body` findings, each flagged body byte-identical to the predecessor's | Zero findings |
| `validate-release`, one-scope selector, `complete-expression-dates-v1` | Passes once the successor's content-baseline entry exists (below); the nine findings are the only errors without it | Zero errors, zero warnings |
| `scripts/audit_release_scope_self_containment.py` | Zero residuals | Zero residuals |
| `scripts/validate_citation_paths.py` on predecessor plus successor | No new unique path; no ratchet moves; no identity drift | Same |

### Recovery content baseline

The nine findings sit in generic HTML rows outside the changed eCFR sections:
`block-3` and `block-51` to `block-54` under
`us/regulation/recovery/release-scope-us-regulation-2026-05-10-snap-7-cfr-273/`,
and `block-5` and `block-12` under each of the two `2026-06-03-cms-2454-ifc`
document roots. The predecessor's entry in `manifests/release-content-baseline.json`
already records them. This PR adds the same nine findings for the successor,
pinned to its provisions SHA-256
`495d76f0d8aa2f58e197049a5b194088a55b5fbf1867920d5a9f585da4fdb45a` and inventory
SHA-256 `b2aa4ddb0f71f4f74119e33ecd9abf07bf35760e94e0b01b916c96220646c0ca`, with
`content-check --update-baseline` after signing and locking, then checks it with
`content-check --check-baseline`.

### Tests

`tests/test_repro_ecfr_section_text_successors.py` (39 cases, synthetic
fixtures, no corpus fetch) covers every guard above; each guard has a test that
fails without that guard. A Hypothesis property generates row sets and
checks that every non-body field of every row equals the predecessor's after the
permitted version, source-prefix and identity mapping. The full suite runs in CI.

## Release hand-off

In each new release lineage, replace each predecessor with its successor; never
select both, since they carry the same citations. Recovery appears in the union
and the rulespec-us pin lineages; the 374-row `26-1` scope appears in the W6/W7
union lineage and not in the current separate-filing pin. Selector changes,
publication, activation and rulespec-us re-pins happen in separate PRs.
