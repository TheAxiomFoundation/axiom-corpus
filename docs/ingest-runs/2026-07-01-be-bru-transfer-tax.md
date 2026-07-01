# 2026-07-01 Brussels Transfer-Tax Article Corpus

## Scope

Snapshots current Brussels-Capital inheritance-tax and gift-tax article text
from SPF Finances FisconetPlus after identifying the relevant Moniteur
publication for the 6 July 2023 Brussels ordinance.

Included provisions:

- Code des droits de succession article 48: Brussels succession-duty rate
  tables.
- Code des droits d'enregistrement article 131: Brussels immovable and movable
  gift-duty rates.
- Code des droits d'enregistrement article 131bis: movable-gift exemption
  context, retained for later special-rule encoding.

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-01-be-bru-transfer-tax \
  --manifest manifests/be-bru-transfer-tax-fisconet-official-documents.yaml
```

## Result

- Jurisdiction: `be-bru`
- Document class: `statute`
- Source files: 3
- Provisions written: 6
- Coverage: complete
- Coverage path:
  `data/corpus/coverage/be-bru/statute/2026-07-01-be-bru-transfer-tax.json`

FisconetPlus returns article bodies as base64 HTML inside JSON. The manifest
uses `json_html_base64` and `json_html_as_single_block` so each article remains
a single citation block.
