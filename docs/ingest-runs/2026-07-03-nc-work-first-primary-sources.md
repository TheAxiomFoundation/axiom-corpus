# 2026-07-03 North Carolina Work First Primary Sources

## Scope

Adds source-first corpus coverage needed before North Carolina Work First
RuleSpec encoding for PolicyEngine parity.

The upstream source hierarchy identified for the current cash assistance
calculation is:

- North Carolina General Statutes section 108A-27.01 from the official North
  Carolina General Assembly site. This statute defines the Work First net family
  annual income eligibility standards and states that the payment level is 50%
  of the standard of need.
- North Carolina DHHS Work First Manual section 114, Income and Budgeting, from
  the official NCDHHS WF Policies/Manuals page. This manual provides the
  monthly payment calculation, monthly need-standard table through household
  size 14, additional-person amount, minimum-payment rule, and countable-income
  treatment needed for operational parity.

The existing state-statute completion queue says the productionized North
Carolina statute release uses a CIC source and should prefer a primary official
source if rebuilt. This run therefore attempts to snapshot the official NCGA
statute directly rather than relying on the existing nonlocal CIC-backed
release.

## Commands

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-nc-work-first-statute \
  --manifest manifests/us-nc-work-first-statute-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --expression-date 2026-07-03
```

```bash
uv run --project . axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-nc-work-first-manual \
  --manifest manifests/us-nc-work-first-manual-official-documents.yaml \
  --source-as-of 2026-07-03 \
  --expression-date 2024-01-01
```

## Result

- North Carolina General Statutes section 108A-27.01 (`us-nc` / `statute`)
  - Version: `2026-07-03-nc-work-first-statute`
  - Result: blocked
  - The official NCGA URL returned HTTP 403 to the corpus extractor on
    2026-07-03, even with the manifest-controlled browser user agent. The
    statute text is visible through browser/search fetches, but no statute
    corpus rows were hand-written and this branch does not rely on the existing
    nonlocal CIC-backed state-statute release for PE parity encoding.
- North Carolina DHHS Work First Manual section 114 (`us-nc` / `manual`)
  - Version: `2026-07-03-nc-work-first-manual`
  - Source files: 1
  - Extraction: top-level Work First manual sections I-XVII, with
    citation-safe lowercase section labels
  - Provisions written: 18
  - Coverage: complete
  - Access note: the official PDF URL is fetchable with `curl` and a browser
    user agent, so the manifest uses the corpus `range_backend: curl` request
    mode instead of a local-only source file.

North Carolina Work First RuleSpec encoding should wait for a primary-official
NCGA statute snapshot or an explicitly approved official-source workaround
before asserting full source hierarchy compliance. The manual corpus scope is
ready for the operational formula/details layer once the statute source is
available.

## Validation

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... \
  uv run --project . axiom-corpus guard-ingested --base-ref origin/main --json
```

```bash
uv run --extra dev --project . python -m pytest -q tests/test_corpus_documents.py
```
