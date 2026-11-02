# LIHEAP FY 2026 state and territory plans

Date: 2026-09-10
Program: LIHEAP (board Year 1 list; `manifests/liheap-agent-queue.yaml`)

Source: ACF LIHEAP Clearinghouse index, https://liheapch.acf.gov/stateplans.htm
(HHS Administration for Children and Families, Office of Community Services).
One "Detailed Model Plan (LIHEAP)" PDF per grantee, report period
2025-10-01 to 2026-09-30: 51 states + DC under `/docs/2026/state-plans/XX_Plan_2026.pdf`,
AS, GU, MP, PR under `/sites/default/files/webfiles/docs/2026/state-plans/`. VI is not on
the index. Agency policy manuals and delegation letters on the same index are a separate
document family, not ingested here.

Scope: 55 jurisdictions × 1 document, document_class `policy`, citation path
`us-xx/policy/acf/liheap-plan/fy2026`, one provision per form section (1–20) plus the root.

Extraction: `labeled_sections`, heading `^Section (?P<label>\d{1,2})\s*[-:]\s*(?P<heading>\S.*)$`,
`start_after_pattern` on the OLDC table of contents ("Plan Attachments"), form headers and
page footers dropped. Section 20 absorbs the trailing Assurances and Plan Attachments
pages; split them in a later revision if encoders need them addressable.

TLS: the server presents only its leaf certificate (issuer Entrust DV TLS Issuing RSA CA 2,
root Sectigo Public Server Authentication Root R46). `data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem`
is that public intermediate, fetched from the leaf's AIA URL. Extraction ran with
`REQUESTS_CA_BUNDLE` = certifi + that file. Verification was not disabled.

Counts: 55 scopes, 1,155 provisions (21 each), coverage `complete: true` for every
scope, 0 missing, 0 extra, 0 duplicate citation paths. Smoke runs: RI, AL.

Artifacts (unsigned, awaiting controller):

- `data/corpus/sources/us-xx/policy/2026-09-10/official-documents/us-xx-acf-liheap-plan-fy2026.pdf`
- `data/corpus/inventory/us-xx/policy/2026-09-10.json`
- `data/corpus/provisions/us-xx/policy/2026-09-10.jsonl`
- `data/corpus/coverage/us-xx/policy/2026-09-10.json`

Rebuild:

```bash
uv run python scripts/build_liheap_state_plan_manifests.py
export REQUESTS_CA_BUNDLE=$PWD/data/certs/liheapch-ca-bundle.pem
for m in manifests/us-*-liheap-state-plan-fy2026.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-10 \
    --manifest $m --source-as-of 2026-09-10 --expression-date 2025-10-01
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"` → 265 passed.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2). After publication the sections
become navigation nodes and axiom-encode can cut a LIHEAP encoding queue; until then the
encoding dashboard shows LIHEAP at stage "registered" with 55 documents and no section count.
