# 2026-07-02 Utah FEP Official Regulation Corpus

## Scope

Adds the official Utah Administrative Code source for R986-200, Family
Employment Program. This regulation is the higher-authority source for the FEP
payment calculation path; the DWS eligibility manual table remains the source
for Department-published SNB/payment-standard dollar values.

Source:

- Utah Office of Administrative Rules, R986-200 current HTML.
  - Rule id: 2196
  - Reference number: R986-200
  - Date of last change: 2022-10-24
  - Notice of continuation: 2025-08-14
  - HTML download handle: `uac-html/1a059e78-4927-4528-9bcd-97c534cd51cf.html`
  - API source URL: `https://adminrules.utah.gov/api/public/getfile/uac-html/1a059e78-4927-4528-9bcd-97c534cd51cf.html/R986-200.html`

## Command

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-ut-fep-official-documents \
  --manifest manifests/us-ut-fep-official-documents.yaml \
  --source-as-of 2026-07-02 \
  --expression-date 2026-07-02
```

## Result

- Jurisdiction/document class: `us-ut` / `regulation`
- Source files: 1
- Provisions written: 2
- Coverage: complete

The official site returns the JavaScript app shell to Python `requests` for the
download endpoint, but returns the actual rule HTML to `curl`. The manifest
therefore uses the extractor's curl-backed fetch path. The generated regulation
block includes section R986-200-239, including the gross-income, SNB, deduction,
net-income, and payment-standard formula language needed for the Utah FEP
encoding path.
