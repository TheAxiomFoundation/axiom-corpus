# Canada section 338 temporary suspension proclamation

This local source-first run retains and extracts the signed White House
proclamation dated August 18, 2026, temporarily suspending for three days the
additional section 338 duties imposed by Proclamations 11046, 11047, and
11048. It is a White-House-only scope pending a later Federal Register
rendition upgrade.

## Scope

| Version | Citation root | Source | Provisions |
| --- | --- | --- | ---: |
| `2026-08-18-canada-338-suspension` | `us/rulemaking/white-house/2026-08-18/canada-338-suspension` | White House proclamation HTML | 18 |

The 18 provisions comprise one document root and 17 citable paragraphs. The
operative paragraph amending the Annex-II chapeaux and changing the effective
date from August 19 to August 22, 2026 is:

`us/rulemaking/white-house/2026-08-18/canada-338-suspension/clause-1`

The agency implementation and collection-suspension direction is separately
citable at `us/rulemaking/white-house/2026-08-18/canada-338-suspension/clause-2`.

## Source and provenance

- Official URL: `https://www.whitehouse.gov/presidential-actions/2026/08/temporary-suspension-of-additional-duties-to-offset-canadian-discrimination-against-the-commerce-of-the-united-states-with-respect-to-alcoholic-beverages-dairy-and-motor-vehicles/`
- Fetcher: tariff parity coordinator.
- Fetch time: 2026-08-19 15:23 ET.
- Staged filename: `wh-2026-08-18-canada-338-suspension.html`.
- Staged and retained size: 305,024 bytes.
- Staged and retained SHA-256: `252d6873bd938e3e8e571d5f2d10df3f09eef482d0911080eb432a77a192d1ac`.
- Retained path: `data/corpus/sources/us/rulemaking/2026-08-18-canada-338-suspension/official-documents/wh-2026-08-18-canada-338-suspension.html`.

The reproducer verifies the byte size and digest before extraction. It selects
the White House `entry-content` container and emits each non-empty
proclamation paragraph as a citable provision, without modifying source text.
It also asserts the operative Annex-II chapeau amendment, new effective date,
and collection-suspension text.

## Reproduce

Initial extraction from the coordinator-staged bytes:

```bash
UV_CACHE_DIR=/tmp/axiom-uv-cache uv run --extra dev python \
  scripts/repro/us_s338_canada_suspension.py \
  --base data/corpus \
  --source-path /Users/maxghenis/PolicyEngine/_tariff-p5/b1/canada-338-staging/wh-2026-08-18-canada-338-suspension.html
```

Once retained, the same extraction is reproducible without the external
staging path:

```bash
UV_CACHE_DIR=/tmp/axiom-uv-cache uv run --extra dev python \
  scripts/repro/us_s338_canada_suspension.py \
  --base data/corpus
```

## Verification

- Source digest and byte size match the coordinator handoff.
- Inventory, provisions, and coverage contain 18 paths; coverage is complete
  with `source_count=18`, `provision_count=18`, and `matched_count=18`.
- The retained source is byte-identical to the staged source.
- A second extraction from the retained source produced byte-identical source,
  inventory, provisions JSONL, and coverage artifacts.
- Focused reproducer lint and execution passed.

## Deferred publication work

This run is local ingest only. The Federal Register rendition upgrade will be
performed when that official rendition is available. Ed25519 signing,
protected publication, R2 upload, Supabase loading, and release activation are
later separately credentialed publication steps; none are performed here.
