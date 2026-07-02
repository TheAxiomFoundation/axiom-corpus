# Belgium PIT Autonomy-Factor Ingest

Run date: 2026-07-02

Manifest:

- `manifests/be-pit-autonomy-factor-official-documents.yaml`

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-07-02-be-pit-autonomy-factor \
  --manifest manifests/be-pit-autonomy-factor-official-documents.yaml \
  --source-as-of 2026-07-02 \
  --request-timeout 45
```

Scope:

- Special Law of 16 January 1989, Article 5/2, defining reduced State tax as
  State tax less State tax multiplied by the autonomy factor.
- Article 5/2, section 2, setting the federal-legislation sequence used to
  obtain State tax before the autonomy-factor reduction.
- Royal Decree of 19 December 2017, Article 1, fixing the definitive autonomy
  factor at 24.957 percent.
- Royal Decree of 19 December 2017, Article 2, applying that decree to income
  taxes from assessment year 2018.

Notes:

- `Justel` is used as the consolidated article locator. Provision records keep
  the corresponding Moniteur/EJustice legal authority URLs where available.
- This source slice supports the Belgium PIT EUROMOD oracle pilot; it is not a
  complete regional personal-income-tax ingestion.
