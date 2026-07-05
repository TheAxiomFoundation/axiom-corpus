# 2026-07-03 Maryland TCA Primary Sources

## Scope

Adds source-first corpus coverage for Maryland Temporary Cash Assistance before
RuleSpec encoding for PolicyEngine parity.

The source hierarchy for the current TCA amount is not a direct copy from the
COMAR payment table:

- Maryland Human Services Code section 5-312 provides the TCA entitlement and
  eligibility frame.
- Maryland Human Services Code section 5-316 requires sufficient funding so
  combined TCA and SNAP benefits meet the statutory minimum-living-level floor.
- COMAR 07.03.03.13 provides the countable-income, earned-income disregard,
  care deduction, and benefit amount formula.
- COMAR 07.03.03.17 is still the current regulation page, but its table states
  "Effective November 1, 2013" values. It should not be used alone for 2025
  PolicyEngine parity.
- Maryland DHS FIA Information Memo 25-12 is the current official agency
  guidance source for the January 1, 2025 TCA, TDAP, and RCA benefit increase
  that PolicyEngine uses.

## Commands

```bash
uv run --project . axiom-corpus extract-maryland-comar \
  --base data/corpus \
  --version 2026-07-03-md-tca-comar \
  --only-title 07 \
  --only-subtitle 03 \
  --only-chapter 03 \
  --source-as-of 2026-07-03 \
  --expression-date 2026-07-03
```

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-md-tca-statutes \
  --manifest manifests/us-md-tca-statutes-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --expression-date 2026-07-03
```

## Result

- Maryland Human Services sections 5-312 and 5-316 (`us-md` / `statute`)
  - Version: `2026-07-03-md-tca-statutes`
  - Source files: 2
  - Provisions written: 6
  - Coverage: complete
- COMAR title 07, subtitle 03, chapter 03 (`us-md` / `regulation`)
  - Version:
    `2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03`
  - Source files: 6
  - Provisions written: 31
  - Coverage: complete
  - Citation-path grammar note: this scope adds the generated collection root
    `us-md/regulation`, so the reviewed collection-root ratchet rises from 8
    to 9.

## Guidance Source

The focused guidance manifest
`manifests/us-md-tca-guidance-official-documents.yaml` records DHS FIA IM
25-12:

- Canonical DHS URL:
  https://dhs.maryland.gov/documents/FIA/Action%20Transmittals-AT%20-%20Information%20Memo-IM/AT-IM2025/25-12%20IM%202025%20TCA%20TDAP%20RCA%20Benefit%20Increase.pdf
- Official DHR alias used as `download_url`:
  https://www.dhr.maryland.gov/documents/FIA/Action%20Transmittals-AT%20-%20Information%20Memo-IM/AT-IM2025/25-12%20IM%202025%20TCA%20TDAP%20RCA%20Benefit%20Increase.pdf

The official document is visible through public search indexing and the browser
fetch path, and the indexed text confirms the January 1, 2025 benefit increase
and the household-size-three increase from $727 to $753. The July 3 unattended
local HTTP attempt timed out, so no generated corpus rows were hand-written at
that time. A July 5 retry succeeded through the manifest-controlled range fetch.

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-05-md-tca-guidance \
  --manifest manifests/us-md-tca-guidance-official-documents.yaml \
  --source-as-of 2026-07-05 \
  --expression-date 2026-07-05
```

Result:

- Maryland DHS FIA Information Memo 25-12 (`us-md` / `guidance`)
  - Version: `2026-07-05-md-tca-guidance`
  - Source files: 1
  - Provisions written: 7
  - Coverage: complete

Maryland TCA RuleSpec encoding can now use the statute, COMAR, and DHS IM 25-12
source graph before asserting 2025 PolicyEngine parity.

## Validation

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... \
  uv run --project . axiom-corpus guard-ingested --base-ref origin/main --json
```
