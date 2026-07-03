# 2026-07-03 Iowa FIP Primary Sources

## Scope

Adds source-first corpus coverage for Iowa Family Investment Program (FIP)
administrative rules before RuleSpec encoding for PolicyEngine parity.

Iowa Code chapter 239B is already covered by the production Iowa Code statute
adapter. These administrative rules are the upstream state rule layer for FIP
eligibility, countable income, need standards, payment rules, overpayment
recovery, diversion, and PROMISE JOBS participation requirements.

## Sources

- Iowa Administrative Code Chapter 441-40, Application for Aid.
- Iowa Administrative Code Chapter 441-41, Granting Assistance.
- Iowa Administrative Code Chapter 441-45, Payment.
- Iowa Administrative Code Chapter 441-46, Recovery of Assistance Overpayment.
- Iowa Administrative Code Chapter 441-47, Diversion.
- Iowa Administrative Code Chapter 441-93, PROMISE JOBS Program.

The PDFs are served by the Iowa Legislature from the official Iowa
Administrative Code publication dated June 24, 2026.

## Command

```bash
uv run axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-ia-fip-admin-rules \
  --manifest manifests/us-ia-fip-admin-rules.yaml
```

## Result

- Jurisdiction: `us-ia`
- Document class: `regulation`
- Version: `2026-07-03-ia-fip-admin-rules`
- Source files: 6
- Provisions written: 64
- Coverage: complete

The section regex requires a real title-case rule heading so cross-references
such as `441-93.13(239B) and 441-93.14(239B)` are not misclassified as new
rule sections. Key parity targets are available at paths including
`us-ia/regulation/iac/441/41/41.27`,
`us-ia/regulation/iac/441/41/41.28`,
`us-ia/regulation/iac/441/45/45.26`, and
`us-ia/regulation/iac/441/45/45.27`.

## Validation

```bash
uv run axiom-corpus extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-ia-fip-admin-rules \
  --manifest manifests/us-ia-fip-admin-rules.yaml
```

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... \
  uv run axiom-corpus guard-ingested --base-ref origin/main --json
```
