# Belgium Worker Work-Bonus Ingest

Run date: 2026-07-02

Manifest:

- `manifests/be-worker-work-bonus-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-02-be-worker-work-bonus \
  --manifest manifests/be-worker-work-bonus-official-documents.yaml \
  --source-as-of 2026-07-02 \
  --request-timeout 45

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-be-cnt-minimum-wage \
  --manifest manifests/be-cnt-minimum-wage-official-documents.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-be-onss-work-bonus \
  --manifest manifests/be-onss-work-bonus-official-documents.yaml
```

Scope:

- Law of 20 December 1999, Article 2, establishing the employee work-bonus
  contribution reduction and A/B statutory split.
- Royal Decree of 17 January 2000, Article 1, implementing the monthly
  work-bonus formula.
- Royal Decree of 5 March 2024, Article 1, replacing the Article 1 formula with
  the current A/B calculation effective 1 April 2024.
- SPF Emploi salaires-minimums pages for Conseil National du Travail, effective
  1 January 2025 and 1 February 2025, stating the CCT 43 RMMMG amounts used by
  the 2025 work-bonus formula.
- ONSS DMFA 2025/2 administrative instructions, work-bonus page, stating the
  employee A/B thresholds, maximum reductions, and alpha coefficients
  applicable from 1 February 2025.

Notes:

- `Justel` is used as the consolidated article locator. Provision records keep
  the corresponding Moniteur ELI as the legal authority URL.
- This is a formula slice for RuleSpec and EUROMOD household-level oracle work;
  it is not a complete payroll-administration ingestion.
