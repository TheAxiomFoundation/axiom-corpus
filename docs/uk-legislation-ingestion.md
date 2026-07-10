# UK Legislation Ingestion

Issue 95 establishes a source-first ingestion track for current UK legislation
from legislation.gov.uk. The track is separate from RuleSpec encoding and from
non-legislation guidance, manuals, notices, and rate tables.

## Scope

The durable corpus artifacts for this track are:

- `data/corpus/sources/uk/{statute,regulation}/...`
- `data/corpus/inventory/uk/{statute,regulation}/...`
- `data/corpus/provisions/uk/{statute,regulation}/...`
- `data/corpus/coverage/uk/{statute,regulation}/...`
- signed `.axiom/ingest-manifests/uk/{statute,regulation}/...`

The immutable pilot selector is
`manifests/releases/uk-legislation-pilot.json`, with queue metadata in
`manifests/uk-legislation-gov-current-pilot.yaml`. Publication produces a
signed content-addressed object; it is not copied into a mutable aggregate.

## Pilot

The pilot is intentionally bounded to existing PE-UK and RuleSpec-UK relevant
current revised CLML provision artifacts. It promotes only official
legislation.gov.uk CLML scopes with complete coverage and signed ingest
manifests. Standalone fixture scopes that duplicate a broader published scope
remain available for extractor tests, but are not added to release manifests.

The pilot excludes:

- GOV.UK, HMRC, DWP, DfE, and other non-legislation guidance or manuals.
- Lex API artifacts until they are re-extracted or mirrored as official
  legislation.gov.uk CLML.
- Legacy HTML compatibility artifacts until they are re-extracted as CLML.
- Historical, made-only, amending, private, and local legislation unless needed
  for current-law interpretation.

## Expansion Plan

1. Resolve PE-UK and RuleSpec-UK legislation.gov.uk references into explicit
   section, regulation, article, schedule, or paragraph CLML citations.
2. Re-extract any legacy HTML or Lex-backed UK legislation artifacts as official
   legislation.gov.uk CLML before promotion.
3. Expand in bounded topic batches: tax, benefits, social security, childcare,
   pensions, housing, transport duties, and devolved benefit/tax programs.
4. Keep guidance, manuals, rate pages, model assumptions, data construction
   inputs, and local Council Tax Reduction schemes on separate document-family
   tracks.
5. For each successful batch, write source, inventory, provisions, coverage,
   and a signed ingest manifest before cutting a new immutable named release.

This lets the UK corpus grow from PE-discovered legislation toward a broader
current revised legislation.gov.uk corpus without treating PE values as source
truth.
