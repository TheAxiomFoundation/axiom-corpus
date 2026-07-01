# 2026-07-01 Walloon Transfer-Tax Article Corpus

## Scope

Snapshots current Walloon inheritance-tax and gift-tax article text from SPF
Finances FisconetPlus after following official Wallex code locators for the
succession and registration-duty codes.

Included provisions:

- Code des droits de succession article 48: Walloon succession-duty rate
  tables. The article body includes future 2028 law plus the current 2026
  table.
- Code des droits d'enregistrement article 131: Walloon immovable gift-duty
  rates. The article body includes future 2028 law plus the current 2026 table.
- Code des droits d'enregistrement article 131bis: Walloon movable gift-duty
  rates.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-wal-transfer-tax \
  --manifest manifests/be-wal-transfer-tax-fisconet-official-documents.yaml
```

## Result

- Jurisdiction: `be-wal`
- Document class: `statute`
- Source files: 3
- Provisions written: 6
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-wal/statute/2026-07-01-be-wal-transfer-tax.json`

FisconetPlus returns article bodies as base64 HTML inside JSON. The manifest
uses `json_html_base64` and `json_html_as_single_block` so each article remains
a single citation block.
