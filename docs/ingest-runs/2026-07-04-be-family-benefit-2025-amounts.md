# Belgium 2025 Family-Benefit Amounts Ingest

Run date: 2026-07-04

Manifest:

- `manifests/be-family-benefit-2025-amounts-official-documents.yaml`

Commands:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-family-benefit-2025-amounts \
  --manifest manifests/be-family-benefit-2025-amounts-official-documents.yaml \
  --only-source-id be-bru-iriscare-family-benefit-scale-2025-02 \
  --source-as-of 2026-07-04 \
  --allow-incomplete

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-family-benefit-2025-amounts \
  --manifest manifests/be-family-benefit-2025-amounts-official-documents.yaml \
  --only-source-id be-wal-aviq-family-benefit-scale-2025-02 \
  --source-as-of 2026-07-04 \
  --allow-incomplete

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-be-family-benefit-2025-amounts \
  --manifest manifests/be-family-benefit-2025-amounts-official-documents.yaml \
  --only-source-id be-vlg-gpedia-start-amount-decision-2025-112 \
  --source-as-of 2026-07-04 \
  --allow-incomplete
```

Scope:

- Brussels Iriscare/Iripedia February 2025 family-benefit amount page,
  including Article 16 birth-allowance amounts.
- Walloon AVIQ February 2025 family-benefit amount scale, including the birth
  premium amount.
- Flemish GPedia decision 2025/112, used as official numeric grounding for the
  2025 start amount after the primary Groeipakket January 2025 amount PDF
  blocked automated download with HTTP 403.

Notes:

- The upstream legal authorities remain the regional statutes cited in the
  manifest metadata: Brussels ordinance of 25 April 2019 Article 16, Flemish
  decree of 27 April 2018 Article 9, and Walloon decree of 8 February 2018
  Article 7.
- Extracted provision rows included the values used by the Belgium
  birth-allowance RuleSpec oracle slice: Brussels first/multiple and later-child
  amounts, the Flemish start amount, and the Walloon birth premium.
- The primary Flemish Groeipakket amount schedule URL is retained in metadata as
  `blocked_primary_amount_schedule_url`; rerun that source when automated access
  is available.
