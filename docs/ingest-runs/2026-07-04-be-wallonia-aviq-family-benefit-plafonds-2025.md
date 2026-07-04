# Wallonia AVIQ 2025 Family-Benefit Income Ceilings Ingest

Run date: 2026-07-04

Official source:

- AVIQ, `Baremes consolides au 01/02/2025 - Plafonds 01/07/2025`
- `https://aviqkid.aviq.be/%2FDocuments%2Fassets%2Fmontants%2FBar%C3%A8mes%20consolidi%C3%A9s%20au%2001%2002%202025%20-%20Plafonds%2001%2007%202025.pdf`

Scope:

- Adds a newer `source_as_of: 2025-07-01` AVIQ guidance extract under the existing Wallonia family-benefit amount-scale citation paths.
- Page 1 grounds the updated first-ceiling reference for pre-2020 child-benefit supplements.
- Page 4 grounds the post-2020 base, age-supplement, and social-supplement amounts.
- Page 6 grounds the updated annual household income ceilings for rights from 2025-07-01 through 2026-06-30: first ceiling 34,000.47 EUR and second ceiling 54,867.79 EUR.

Notes:

- The existing `2026-07-04-be-family-benefit-2025-amounts-be-wal-aviq-family-benefit-scale-2025-02` extract came from the February 2025 amount table and still carried 2022-income ceilings for the 2024-07-01 to 2025-06-30 right period.
- This extract keeps the same canonical citation paths and a later `source_as_of`, so local source lookup selects the July 2025 ceiling records for RuleSpec numeric grounding.

Validation:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path("data/corpus/provisions/be-wal/guidance/2026-07-04-be-wallonia-family-benefit-amount-scale-2025.jsonl")
for line in p.read_text().splitlines():
    json.loads(line)
PY

uv run --project /Users/maxghenis/TheAxiomFoundation/axiom-encode python - <<'PY'
from axiom_encode.harness.validator_pipeline import (
    _fetch_local_corpus_source_text,
    extract_numbers_from_text,
)
text = _fetch_local_corpus_source_text(
    "be-wal/guidance/aviq/family-benefits/amount-scale-2025-02/page-6"
)
assert 34000.47 in extract_numbers_from_text(text)
assert 54867.79 in extract_numbers_from_text(text)
PY
```
