# 20 CFR part 416 with its Appendix to Subpart K

The final capture ran on 2026-10-29 with main `b92bd3033c0bed9c1b7ce9a1b37ff3d9476f69fb`, after #828
(subpart appendix support) and #832 (section captions and word breaks) merged. It writes the whole-part successor
`us/regulation/2026-10-12-with-appendices-title-20-part-416`: all 622 predecessor rows, two repaired section bodies,
and the Appendix to Subpart K. The version keeps this PR's original capture name.

"Appendix to Subpart K of Part 416" lists types of income that federal laws other than the Social Security Act
exclude under SSI. The released `us/regulation/2026-09-11-title-20-part-416` skipped it because the previous
`extract-ecfr --include-appendices` adapter rejected subpart-scoped identifiers
(`docs/ingest-runs/2026-09-11-federal-cfr-followon-parts.md`). #828 lets the adapter take it at
`us/regulation/20/416/subpart-K/appendix`, a level-2 child of `us/regulation/20/416/subpart-K`.

Release validation needs every parent in the same scope, and a profiled release rejects duplicate citation paths
across selected scopes. The successor therefore replaces the predecessor in a release selector.

## Point in time: 2026-09-09

The predecessor's version prefix records its run date. Its rows carry `source_as_of` and `expression_date`
2026-09-09: on 2026-09-11 the Versioner API served title 20 only through 2026-09-09. The successor uses that same
point in time (`--as-of 2026-09-09 --expression-date 2026-09-09`). The final capture's part XML and title structure
JSON match both predecessor lock entries byte-for-byte. The two changed section bodies reflect #832's rendering
fixes on those same source bytes.

## Capture

```bash
uv run axiom-corpus-ingest inventory-ecfr --base data/corpus \
  --version 2026-10-12-with-appendices --as-of 2026-09-09 \
  --only-title 20 --only-part 416 --include-appendices
uv run axiom-corpus-ingest extract-ecfr --base data/corpus \
  --version 2026-10-12-with-appendices --as-of 2026-09-09 \
  --expression-date 2026-09-09 --only-title 20 --only-part 416 --include-appendices --workers 1
```

The final run used one extraction worker under the host reservation; the worker count does not change output.
`ecfr_run_id` appends `title-20-part-416`, giving the scope
`2026-10-12-with-appendices-title-20-part-416`.

## Result against the locked predecessor

A row-by-row comparison checks every field of every common row, verifies the five predecessor files against their
lock, and checks the final appendix directly against the retained XML.

- 623 rows: the 622 predecessor rows keep their relative order, plus the appendix at its subpart position.
- All 622 common rows change only `version` and `source_path`, except the two section bodies listed below.
  IDs, parent IDs, dates, source URLs, headings, metadata and all other fields match.
- Of 599 sections, 597 keep identical bodies. After mapping the version and source path, 620 common rows match
  in every field. No row disappears.
- The inventory adds the appendix and keeps all 622 existing entries in order; only their source paths change.
  Coverage reports 623 source entries, 623 provisions and 623 matches, with no missing, extra or duplicate entries.

| Citation path | Predecessor characters | Successor characters | Exact body change |
| --- | ---: | ---: | --- |
| `us/regulation/20/416/974` | 12,895 | 12,922 | Add `[Table caption: Table 1]`; change `earningsaveraged` to `earnings averaged`. |
| `us/regulation/20/416/1112` | 5,458 | 5,484 | Add `[Table caption: Table 1]`. |

The new row has citation path `us/regulation/20/416/subpart-K/appendix`, `kind` appendix, level 2,
parent `us/regulation/20/416/subpart-K`, ordinal 1,000,000, and legal identifier
`20 CFR part 416, subpart K, appendix`. Its heading reads "List of Types of Income Excluded Under the SSI Program
as Provided by Federal Laws Other Than the Social Security Act". Its 22,582-character body covers five categories:
I Food, II Housing and Utilities, III Education and Employment, IV Native Americans, V Other.

The independent text check removes only `HEAD` and the bracketed `CITA` source note from the appendix's source
`DIV9`, concatenates its XML text with ElementTree, and compares the word sequence with the final body. Both
sequences match: 3,952 words counted with `\b\w+\b`. Whitespace-delimited token sequences also match exactly.

All five final output files match the independent research capture byte-for-byte:

| Artifact under `data/corpus/` | Bytes | SHA-256 |
| --- | ---: | --- |
| `sources/us/regulation/2026-10-12-with-appendices-title-20-part-416/ecfr/title-20-part-416.xml` | 1,745,553 | `11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26` |
| `sources/us/regulation/2026-10-12-with-appendices-title-20-part-416/ecfr/title-20.structure.json` | 3,981,872 | `9587a2f15038535028f87ccbe8d81318db2cf2f7e1abdf781e41ece2da3d1d55` |
| `inventory/us/regulation/2026-10-12-with-appendices-title-20-part-416.json` | 545,967 | `fbf63e1b08dcc8c40f71a2f7a964fa2a4e1befb32e27d38ed1de08876f5da2dc` |
| `provisions/us/regulation/2026-10-12-with-appendices-title-20-part-416.jsonl` | 2,087,120 | `7f0aece5f94dc7cbd45f754063c1e5d529541c3581550fbf70a28d55a2fe0cf4` |
| `coverage/us/regulation/2026-10-12-with-appendices-title-20-part-416.json` | 349 | `49ed8d6a199da6825740f84efbedd9f2f21956d8831e18ea5cca22f422aaa21a` |

## Retirement of the wave-5 manifest

#718 wrote `manifests/us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml` (scope
`2026-09-15-title-20-part-416-appendix-k`), which took the appendix from the eCFR renderer API as an official HTML
document at `us/regulation/20/416/subpart-K/appendix` plus `.../appendix/block-1`. No lock or ingest manifest names
it, and #718 locked none of its eight scopes. Keeping it would let a later wave-5 pass lock a second scope for the
same appendix path. This PR:

- deletes the manifest and removes the `ssi-cfr-416-appendix-k` generator family from
  `scripts/build_federal_guidance_layer_manifests.py`;
- points the SSI queue's eCFR row at the 623-row successor and drops its `appendix_subpart_k_scope` record;
- marks the scope retired at the appendix bullet and Controller list in
  `docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md`.

The needs-closure snapshots (`docs/coverage/needs-closure-2026-09-1{1,4}/`) and wave-5 decisions CSV remain dated
records. The original writer checked the generator removal's callers by hand when its GitNexus index failed to
open: only the script referenced `build_ssi_cfr_416_appendix_k`, `APPENDIX_K_VERSION` and `ECFR_APPENDIX_*`.
The final capture changes no Python symbols.

## Citation-path ratchets

Running the validator in `scripts/validate_citation_paths.py` on the predecessor, successor and their union shows the
delta. Unique uppercase paths increase from 22 to 23, exactly the appendix
path; every other irregular family changes by zero, and no identity drift appears. Repeated versions of the 622
existing paths do not increase the counts.

The [full-main citation-path CI job](https://github.com/TheAxiomFoundation/axiom-corpus/actions/runs/40872379920/job/123442457570)
for `b92bd3033c0bed9c1b7ce9a1b37ff3d9476f69fb` measures 766,165 records and 535,273 unique paths, with all live
counts equal to their tracked baselines. Its uppercase count is 19,561. Adding the measured one-path delta gives
an inferred merged ceiling of 19,562; this PR raises only that numeric baseline in `schema/citation-path.v1.json`.
Other ceilings remain `block_n` 105,419, `page_n` 178,888, `space_segments` 307, `endash_segments` 1,656,
`truncated_segments` 53 and `collection_roots` 10.

CI's merged-tree citation-path scan checks the raised ceiling on this PR.

## Release hand-off

The Axiom engineering hub must select `us/regulation/2026-10-12-with-appendices-title-20-part-416` in place of
`us/regulation/2026-09-11-title-20-part-416`, never both. Nine tracked selectors name the predecessor, from
`us-rulespec-2026-09-13-cms-state-plans-union` through `us-rulespec-2026-10-13-w7-bundle-gaps-union`.
The selector PR owns that replacement. Release cutting, activation and rulespec-us re-pins remain outside this PR.

## Checks

| Check | Result |
| --- | --- |
| `corpus fetch us/regulation/2026-09-11-title-20-part-416` | Five predecessor files, 8,305,439 bytes, all matching the lock. |
| Inventory and extraction commands in Capture | 623 inventory entries and provisions; complete coverage; zero title errors. |
| Row-by-row comparison with the predecessor | As above: 620 common rows equal after the version mapping, two section bodies changed, one appendix added, no row removed. |
| Appendix word sequence against the source `DIV9` | 3,952 words, identical sequence. |
| `validate-release` on a one-scope selector (`complete-expression-dates-v1` profile) | One scope, zero errors, zero warnings. |
| `scripts/audit_release_scope_self_containment.py` on the same selector | Zero parent residuals. |
| `content-check us/regulation/2026-10-12-with-appendices-title-20-part-416` | CONTENT_CHECK_RESULT |
| Citation-path validator on predecessor, successor and union | `uppercase_segments` +1, every other family +0, no identity drift. |
| `ruff check .`, `mypy src/axiom_corpus/corpus`, `towncrier check`, `git diff --check` | Pass. |

The full test suite and the merged-tree citation-path scan run in CI on this PR.
