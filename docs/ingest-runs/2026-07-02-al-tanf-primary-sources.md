# 2026-07-02 Alabama TANF Primary Sources

## Scope

Adds source-first corpus coverage for Alabama TANF before RuleSpec encoding:

- Alabama Code Title 38 from the official ALISON Code of Alabama GraphQL source.
- Alabama Administrative Code Chapter 660-2-2, Aid to Dependent Children, from the official Alabama Administrative Code chapter PDF.

The statute source is the upstream authority layer. The administrative-code
chapter contains the TANF payment and assistance-unit details needed for
PolicyEngine parity work.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-al-code-title-38.yaml
```

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-al-admin-code-660-2-2 \
  --manifest manifests/us-al-admin-code-660-2-2.yaml
```

## Result

- Alabama Code Title 38 (`us-al` / `statute`)
  - Version: `2026-07-02-us-al-title-38`
  - Source files: 51
  - Provisions written: 291
  - Coverage: complete
- Alabama Administrative Code Chapter 660-2-2 (`us-al` / `regulation`)
  - Version: `2026-07-02-al-admin-code-660-2-2`
  - Source files: 1
  - Provisions written: 45
  - Coverage: complete

The source snapshots are stored with the corpus artifacts and signed ingest
manifests cover the generated source, inventory, provision, and coverage files.
