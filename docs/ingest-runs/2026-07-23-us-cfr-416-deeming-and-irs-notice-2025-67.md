# 20 CFR 416 deeming slice and IRS Notice 2025-67

## Scope decision

This ingest uses the explicit-slice option. The downstream grounding scope needs
ten deeming-related sections and four required hierarchy containers, not all
622 non-reserved units in Part 416. Expanding to the full Part would add 608
unapproved rows without improving the requested grounding boundary.

The regulation inventory therefore certifies this explicit 14-row slice, not
the completeness of all Part 416:

```text
us/regulation/20/416
us/regulation/20/416/subpart-K
us/regulation/20/416/1149
us/regulation/20/416/1160
us/regulation/20/416/1161
us/regulation/20/416/1163
us/regulation/20/416/1167
us/regulation/20/416/subpart-L
us/regulation/20/416/1202
us/regulation/20/416/1207
us/regulation/20/416/subpart-R
us/regulation/20/416/1801
us/regulation/20/416/1802
us/regulation/20/416/1806
```

## Official sources

The retained primary-source snapshots are:

| Source | Official URL | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| eCFR Title 20 structure, 2026-07-14 | `https://www.ecfr.gov/api/versioner/v1/structure/2026-07-14/title-20.json` | 3,982,355 | `f3946c95dd8e4c88f51910538b7c99e98f6563fcd667786771c34d14801b1228` |
| eCFR Title 20 Part 416 XML, 2026-07-14 | `https://www.ecfr.gov/api/versioner/v1/full/2026-07-14/title-20.xml?part=416` | 1,745,553 | `11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26` |
| IRS Notice 2025-67 PDF | `https://www.irs.gov/pub/irs-drop/n-25-67.pdf` | 133,701 | `1eea8f141b0cddd182f9f09b3bc8ffad683d27ceb806dfc6da126811dc0a1f8d` |

The IRS also publishes the Notice in
`https://www.irs.gov/irb/2025-49_IRB`.

## Literal reproduction commands

The exact regulation command to record in the ingest manifest is:

```bash
uv run --extra dev python scripts/repro_us_cfr_416_deeming_slice.py --base data/corpus
```

The script reads only the two retained, hash-pinned official eCFR snapshots. It
does not read an existing inventory, provision file, or coverage report. In a
clean internal staging directory it:

1. runs the repository eCFR adapter over the complete retained hierarchy and
   asserts the independent 622-unit source count;
2. applies the exact 14-path allowlist above in adapter/source order;
3. materializes only the four selected containers from their selected official
   descendants; and
4. recomputes coverage before atomically installing the two source snapshots
   and three derived artifacts.

Filtering precedes materialization, so the container bodies contain no
unapproved Part 416 sections. The algorithm
`official-descendant-heading-body-join-v1` concatenates adapter-produced
headings and bodies without editing section text. Its recursive leaf counts are
10 for Part 416, 5 for Subpart K, 2 for Subpart L, and 3 for Subpart R. This
also gives every retained container a body that the exact encoder resolver can
ground.

The existing official-document extractor already writes inventory, provisions,
and coverage for Notice 2025-67. Its literal command is:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-23 \
  --manifest manifests/us-irs-guidance.yaml \
  --only-source-id irs-notice-2025-67
```

There is deliberately no trailing bare `coverage --write`; that would invoke
an unrelated executable and is not part of either reproduction.

## Clean replay proof

A separate destination proves that no pre-existing derived CFR artifact is
reused:

```bash
repro_dir=$(mktemp -d /private/tmp/cfr416-repro.XXXXXX)
uv run --extra dev python scripts/repro_us_cfr_416_deeming_slice.py \
  --source-base data/corpus \
  --base "$repro_dir"
cmp \
  data/corpus/sources/us/regulation/2026-07-23-title-20-part-416/ecfr/title-20.structure.json \
  "$repro_dir/sources/us/regulation/2026-07-23-title-20-part-416/ecfr/title-20.structure.json"
cmp \
  data/corpus/sources/us/regulation/2026-07-23-title-20-part-416/ecfr/title-20-part-416.xml \
  "$repro_dir/sources/us/regulation/2026-07-23-title-20-part-416/ecfr/title-20-part-416.xml"
cmp data/corpus/inventory/us/regulation/2026-07-23-title-20-part-416.json \
  "$repro_dir/inventory/us/regulation/2026-07-23-title-20-part-416.json"
cmp data/corpus/provisions/us/regulation/2026-07-23-title-20-part-416.jsonl \
  "$repro_dir/provisions/us/regulation/2026-07-23-title-20-part-416.jsonl"
cmp data/corpus/coverage/us/regulation/2026-07-23-title-20-part-416.json \
  "$repro_dir/coverage/us/regulation/2026-07-23-title-20-part-416.json"
```

The five reproduced hashes are:

```text
f3946c95dd8e4c88f51910538b7c99e98f6563fcd667786771c34d14801b1228  title-20.structure.json
11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26  title-20-part-416.xml
2dd439932c96eee232a54c737c4b7f5a752f520801f4b342c13d47068386ac33  inventory
b7cbb4a14b218bcbcafa498ac97f4bd912004258e0cd2e6f1fb4d88f88dd794b  provisions
93209bef1ffb0588956fd75290ab0703c67e0c5191f6cfdac95a3577dde08076  coverage
```

Coverage is complete at 14/14 for the regulation slice and 7/7 for the Notice.

## Publication and signing

No R2, Supabase, publication, push, or pull-request write belongs to this run.
The two 2026-07-23 ingest manifests are intentionally absent from the content
branch. The key-bearing main lane must sign both scopes only after the settled
content commit is an ancestor of the signing commit, and no tracked content
change may follow signing.
