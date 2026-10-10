# Kansas 2026 resident individual income-tax core

This scope preserves current official Kansas Revisor primary authority for a
tax-year-2026 full-year-resident individual income-tax pipeline. It includes
the resident definition, tax schedules and annual rate-reduction mechanism,
Kansas Department of Revenue Notice 25-06 establishing that the statutory
reduction conditions were not met and the rates do not change for tax year
2026,
Kansas adjusted gross and taxable income, standard and itemized deductions,
both official personal-exemption amendment versions, the resident credit for
tax paid to another state, the refundable earned-income credit, and the
refundable pass-through-entity credit.

The scope also pins signed 2026 House Bill 2029. That enrolled reconciliation
bill preserves the individual schedules and 79-32,110c rate-reduction
reference in one 79-32,110 version, combines the nonconflicting personal
exemption amendments into one 79-32,121 version, and repeals 79-32,110b and
79-32,121b. The earlier official parallel versions remain in the corpus as
historical source context, but downstream RuleSpec must follow the reconciled
text for tax-year-2026 returns.

The scope also retains enacted 2026 Senate Bill 82. Its first section creates
a nonrefundable credit, with carryforward, for a resident individual's
qualifying lockable gun and ammunition storage expenditures in tax years 2026
through 2028.

This focused scope does not claim that every specialty credit in Kansas law is
captured or that the unavailable 2026 Form K-40 and its ordering instructions
have been published.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-ks-resident-income-tax-core \
  --manifest manifests/us-ks-2026-resident-income-tax-core.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-ks-2026-income-tax-rate-determination \
  --manifest manifests/us-ks-2026-income-tax-rate-determination.yaml
```
