# 26 USC 1401 coordination metadata and operative-authority repair

Release `us-2026-07-24-1401-coordination-repair` corrects the source URLs for
26 U.S.C. 1401 and 3101 and adds the official 26 CFR 1.1401-1 authority that
operationalizes their Additional Medicare Tax coordination.

## Retained official sources

The statute source is the immutable OLRC per-title download current through
Public Law 119-102, except 119-101, as of 2026-07-12:

- URL:
  `https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/xml_usc26@119-102not101.zip`
- ZIP: 8,289,527 bytes; SHA-256
  `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0`
- Exact `usc26.xml` member: 55,856,053 bytes; SHA-256
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`

The regulation source is the official eCFR Title 26 Part 1 XML response as of
2026-07-22:

- URL:
  `https://www.ecfr.gov/api/versioner/v1/full/2026-07-22/title-26.xml?part=1`
- XML: 70,089,620 bytes; SHA-256
  `1e5ca5d86df2ebf303d2df1eb9d162412e549896118779621d41139c9662001a`

No source snapshot is reconstructed. The former reserialized eCFR structure
JSON is not retained or attested.

## Reproducible local generation

Both scopes, including retained source bytes, inventory, provisions, coverage,
and anchors, are reproduced by this single literal command:

```bash
uv run --no-cache --extra dev python scripts/repro/us_1401_coordination_repair.py --base data/corpus
```

The script verifies the three retained source hashes and the OLRC ZIP-member
byte chain before invoking the following scoped corpus commands.

The statute artifacts and source-ID anchors are reproduced by:

```bash
unzip -o \
  data/corpus/sources/us/statute/2026-07-24-1401-coordination-repair-title-26/olrc/xml_usc26@119-102not101.zip \
  -d data/corpus/sources/us/statute/2026-07-24-1401-coordination-repair-title-26/uslm &&
uv run --extra dev axiom-corpus-ingest extract-usc \
  --base data/corpus \
  --version 2026-07-24-1401-coordination-repair \
  --source-xml data/corpus/sources/us/statute/2026-07-24-1401-coordination-repair-title-26/uslm/usc26.xml \
  --title 26 \
  --source-as-of 2026-07-12 \
  --expression-date 2026-07-12 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/xml_usc26@119-102not101.zip \
  --section 1401 \
  --section 3101 \
  --include-title &&
uv run --extra dev axiom-corpus-ingest generate-anchors \
  --provisions data/corpus/provisions/us/statute/2026-07-24-1401-coordination-repair-title-26.jsonl \
  --asserted-parent us/statute/26/1401 \
  --asserted-parent us/statute/26/3101 \
  --output data/corpus/anchors/us/statute/2026-07-24-1401-coordination-repair-title-26.jsonl
```

The regulation artifacts and inferred anchors are reproduced solely from the
retained official XML:

```bash
uv run --extra dev axiom-corpus-ingest extract-ecfr \
  --base data/corpus \
  --version 2026-07-24-1401-coordination-repair \
  --as-of 2026-07-22 \
  --expression-date 2026-07-22 \
  --source-xml data/corpus/sources/us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1/ecfr/title-26-part-1.xml \
  --only-title 26 \
  --only-part 1 \
  --section 1.1401-1 \
  --workers 1 &&
uv run --extra dev axiom-corpus-ingest generate-anchors \
  --provisions data/corpus/provisions/us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1.jsonl \
  --target us/regulation/26/1/1401-1 \
  --output data/corpus/anchors/us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1.jsonl
```

## Result

The statute scope has 21/21 complete coverage: the title, §§ 1401 and 3101, and
all 18 publisher-identified descendants through USLM subparagraph and clause
depth. Its 18 anchors are `machine_asserted` from OLRC source identifiers.

The statutory text is byte-faithful to official USLM. In particular,
26 U.S.C. 1401(b)(2)(B) preserves the enacted `3121(b)(2)` scrivener's error;
it is not silently corrected to `3101(b)(2)`.

The regulation scope has 2/2 complete coverage: Part 1 and § 1.1401-1. Its
normalized section body preserves the official `Note:` and `Example 1.` through
`Example 5.` labels. Under the ratified assertion-frontier policy, the operative
paragraph remains the exact inferred anchor
`us/regulation/26/1/1401-1/d/2/i`, while the official eCFR section remains the
asserted provision identity.

No publication, R2 upload, Supabase load, RuleSpec repository change, push, or
PR mutation is part of this repair. Ingest manifests remain unsigned for the
main lane to sign only after the final attested commit is an ancestor.
