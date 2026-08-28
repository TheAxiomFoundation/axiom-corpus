# USITC HTS 2026 General Note 29: Revision 15 operative text and Revision 17 current check

This source-first run adds the complete USITC General Note 29 for both the
Revision 15 tariff-campaign window and the current Revision 17 check. General
Note 29 is the Dominican Republic-Central America-United States Free Trade
Agreement (DR-CAFTA) note. The Revision 15 scope supplies the missing
primary-source citation required to ground the General Note 29(d)(v) term used
by Revision 15 Chapter 99 Note 52(i); Revision 17 proves that the operative
text remained current on the verification date.

## Official source

- Authority: United States International Trade Commission (USITC).
- Operative campaign release: `2026HTSRev15`, published and effective August
  3, 2026.
- Current comparator release: `2026HTSRev17`, published and effective August
  24, 2026.
- Current-release endpoint:
  `https://hts.usitc.gov/reststop/currentRelease`.
- Release archive:
  `https://www.usitc.gov/harmonized_tariff_information/hts/archive/list`.
- Operative release-pinned PDF:
  `https://hts.usitc.gov/reststop/file?release=2026HTSRev15&filename=General%20Note%2029`.
- Current release-pinned PDF:
  `https://hts.usitc.gov/reststop/file?release=2026HTSRev17&filename=General%20Note%2029`.
- Verification date: August 28, 2026. The current-release endpoint returned
  `2026HTSRev17` immediately before and immediately after extraction.
- Revision 15 retained PDF: 256,665 bytes, 93 pages, SHA-256
  `e450b3281a293bb1956c5889fb3ed86e43a542a9c72084ce240f6d2ec79b58a8`.
- Revision 17 retained PDF: 256,677 bytes, 93 pages, SHA-256
  `59cba6e7e464d8d15bfcdd6b50e0f3256e6c1df4e4dbc8e9baad15627fc5a9dc`.

The release parameters make both source URLs immutable with respect to later
HTS revisions. Each retained file matches an independent direct download made
before corpus extraction. A full 93-page `pdftotext -layout` comparison,
normalizing only the rendered `Revision 15` / `Revision 17` header number,
produced an empty diff. Every extracted provision body likewise matches after
that header normalization. The campaign therefore uses Revision 15 rather than
silently introducing post-window Revision 17 text.

## Corpus scope

Each of these versions contains one document root and all 93 source pages:

- `2026-08-28-usitc-hts-2026-rev15-general-note-29` (operative campaign text)
- `2026-08-28-usitc-hts-2026-rev17-general-note-29` (current comparator)

Both use the citation structure:

- `us/statute/hts/general-note-29`
- `us/statute/hts/general-note-29/page-1` through
  `us/statute/hts/general-note-29/page-93`

General Note 29(d)(v) is wholly preserved on
`us/statute/hts/general-note-29/page-4`. That page defines “textile or apparel
good” by reference to the Annex to the WTO Agreement on Textiles and Clothing,
then enumerates the goods in DR-CAFTA Annex 3.29 that the term excludes.

Each extraction produced 94 inventory records and 94 normalized provision
records. Each coverage report is complete: 94 matched, zero missing, zero
extra, and no duplicate source or provision citations.

## Reproduce

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-08-28-usitc-hts-2026-rev15-general-note-29 \
  --manifest manifests/us-usitc-hts-2026-rev15-general-note-29.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-08-28-usitc-hts-2026-rev17-general-note-29 \
  --manifest manifests/us-usitc-hts-2026-rev17-general-note-29.yaml

uv run --extra dev axiom-corpus-ingest coverage \
  --base data/corpus \
  --source-inventory data/corpus/inventory/us/statute/2026-08-28-usitc-hts-2026-rev15-general-note-29.json \
  --provisions data/corpus/provisions/us/statute/2026-08-28-usitc-hts-2026-rev15-general-note-29.jsonl \
  --jurisdiction us \
  --document-class statute \
  --version 2026-08-28-usitc-hts-2026-rev15-general-note-29
```

## Fail-closed downstream boundary

These scopes ground the General Note 29 legal text, including every explicit
Annex 3.29 exclusion, but they do not by themselves produce a complete six-digit
HTS membership table. General Note 29(d)(v) incorporates the product list in
the Annex to the WTO Agreement on Textiles and Clothing. The authoritative WTO
agreement PDF is:

- `https://www.wto.org/english/docs_e/legal_e/downloads_e/atc_en.pdf`
- legal-text landing page:
  `https://www.wto.org/english/docs_e/legal_e/16-tex_e.htm`
- verified August 28, 2026: 353,581 bytes, 28 PDF pages, SHA-256
  `5df8d1aa23f6e9558250cfc602c52ef86a89ad6936539c6541b918bd104675b1`
- the Annex begins on PDF page 12 and continues through page 28.

That Annex is not included in this change. A minimal source-first
`jurisdiction: wto`, `document_class: other` scope is blocked by a corpus
contract mismatch: `DocumentClass.OTHER` exists in the ingestion model, but
the published citation-path v1.1 schema and its hard-gate test define a closed
set of eight document classes that excludes `other`. Adding it is explicitly a
normative grammar change rather than a data-only ingest. Mapping the treaty to
the `us` jurisdiction would also misstate its issuing authority. The WTO source
therefore needs a separate, reviewed citation-grammar/convention change before
it can be ingested.

RuleSpec must therefore fail closed on positive textile/apparel membership
until the official WTO Annex is separately ingested and the historical HS
codes are mapped to the applicable current HTS lines with an explicit,
reviewable concordance. It must not infer that membership from Yale or from
country of origin. The separate transaction fact that DR-CAFTA duty-free entry
was actually claimed also remains required by Chapter 99 Note 52(i).
