# Illinois 2026 resident individual income-tax core

This scope preserves current official Illinois General Assembly primary
authority for the tax-year-2026 resident individual income-tax pipeline.
Sections 201, 203, 204, 208, 212, 244, and 601 of the Illinois Income Tax Act
cover the 4.95 percent individual rate, base-income modifications, exemptions,
the residential property-tax credit, the earned income credit, the child tax
credit, and the credit for qualifying tax paid to another state.

Public Act 104-0468 is retained as a separate enacted session-law overlay
because the ILCS site warns that recent laws may not yet be incorporated. The
overlay includes the section 203 addition for gain excluded under Internal
Revenue Code section 1202 for tax years ending on and after December 31, 2026,
as well as changes to the pass-through-entity branch. Article 999 makes the
relevant Article 120 effective when the Act became law on June 16, 2026; the
July 1 effective date is limited to Articles 25 and 65.

The scope deliberately retains complete official section bodies rather than
extracting isolated dollar amounts. This keeps the operative qualifications,
limitations, refundability rules, effective dates, and specialty branches
available to RuleSpec consumers. It does not treat tax forms from an earlier
tax year as tax-year-2026 authority.

Artifacts were generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-il-individual-income-tax-resident-core \
  --manifest manifests/us-il-2026-resident-income-tax-core.yaml
```

The result contains 1,631 normalized blocks from eight official documents.
Inventory, provision, and coverage counts are each 1,639, with no missing or
extra citation paths. Retaining the enacted 1,624-page Public Act and seven
section blocks deliberately raises the reviewed citation-path ceilings from
27,112 to 28,736 `page-N` paths and from 19,687 to 19,697 `block-N` paths.
The protected signing wrapper produced the signed ingest manifest at
`.axiom/ingest-manifests/us-il/statute/2026-07-24-il-individual-income-tax-resident-core.json`.
No private signing material was read or written by the ingestion session.
