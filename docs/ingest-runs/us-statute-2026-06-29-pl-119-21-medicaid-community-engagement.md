# Public Law 119-21 Medicaid community engagement

Date: 2026-06-29

Source: GovInfo USLM for Public Law 119-21, section 71119.

This scoped ingest extracts the quoted amendment adding 42 U.S.C.
1396a(xx), because the current US Code Title 42 release used by the Medicaid
corpus includes the conforming cross-reference in 42 U.S.C.
1396a(a)(10)(A)(i)(VIII) but not yet the newly added subsection text.

Artifacts:

- `data/corpus/sources/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement/uslm/PLAW-119publ21.xml`
- `data/corpus/inventory/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement.json`
- `data/corpus/provisions/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement.jsonl`
- `data/corpus/coverage/us/statute/2026-06-29-pl-119-21-medicaid-community-engagement.json`

Rebuild:

```bash
uv run python scripts/extract_pl119_21_medicaid_community_engagement.py
```
