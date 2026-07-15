# Final US release signing commands

Run these commands from the repository root on the reviewed, clean commit. They
replace the unsigned stubs in place. The signer fails closed when
`AXIOM_CORPUS_INGEST_PRIVATE_KEY` is absent.

```bash
: "${AXIOM_CORPUS_INGEST_PRIVATE_KEY:?missing ingest-manifest signing key}"

sign_scope() {
  jurisdiction="$1"
  document_class="$2"
  version="$3"
  UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
    --repo . \
    --base data/corpus \
    --jurisdiction "$jurisdiction" \
    --document-class "$document_class" \
    --version "$version" \
    --command 'uv run python scripts/recover_ingest_batch.py' \
    --output ".axiom/ingest-manifests/${jurisdiction}/${document_class}/${version}.json"
}

sign_scope us form 2026-05-12-cms-medicaid-chip-bhp-eligibility-levels
sign_scope us form 2026-07-13-recovery
sign_scope us guidance 2026-05-01-snap-fy2026-cola
sign_scope us guidance 2026-05-02-irs-rev-proc-2025-32
sign_scope us guidance 2026-05-02-snap-fy2026-income-eligibility-standards
sign_scope us guidance 2026-07-08-snap-fy2024-cola
sign_scope us guidance 2026-07-13-recovery
sign_scope us regulation 2026-05-10-snap-7-cfr-273
sign_scope us regulation 2026-06-03-cms-2454-ifc-42-cfr-435-community-engagement
sign_scope us regulation 2026-06-03-cms-2454-ifc-42-cfr-conforming-amendments
sign_scope us regulation 2026-07-13-recovery
sign_scope us statute 2026-05-10-snap-sections
sign_scope us statute 2026-05-10-tax-sections
sign_scope us statute 2026-07-13-recovery
sign_scope us-al manual 2026-05-27-al-snap-poe-manual
sign_scope us-al manual 2026-07-13-recovery
sign_scope us-al policy 2026-07-13-recovery
sign_scope us-al regulation 2026-05-29
sign_scope us-al statute 2026-07-13-recovery
sign_scope us-az statute 2026-07-13-recovery
sign_scope us-ca guidance 2025-09-03-ca-cdss-acin
sign_scope us-ca guidance 2026-07-13-recovery
sign_scope us-ca regulation 2026-07-13-recovery
sign_scope us-ca statute 2026-07-13-recovery
sign_scope us-co regulation 2026-04-29-10-ccr-2506-1
sign_scope us-co regulation 2026-07-13-recovery
sign_scope us-ct statute 2026-07-13-recovery
sign_scope us-dc statute 2026-07-13-recovery
sign_scope us-de statute 2026-07-13-recovery
sign_scope us-fl manual 2026-05-27-fl-ess-manual
sign_scope us-fl manual 2026-07-13-recovery
sign_scope us-fl regulation 2026-05-29
sign_scope us-fl regulation 2026-07-13-recovery
sign_scope us-ga manual 2026-05-27-ga-snap-manual
sign_scope us-ga manual 2026-07-13-recovery
sign_scope us-hi regulation 2026-05-27-hi-snap-rules
sign_scope us-hi regulation 2026-07-13-recovery
sign_scope us-hi statute 2026-07-13-recovery
sign_scope us-ia statute 2026-07-13-recovery
sign_scope us-id regulation 2026-05-27-id-food-stamp-rules
sign_scope us-id regulation 2026-07-13-recovery
sign_scope us-id statute 2026-07-13-recovery
sign_scope us-il manual 2026-05-27-il-cash-snap-medical-manual
sign_scope us-il manual 2026-07-13-recovery
sign_scope us-il statute 2026-07-13-recovery
sign_scope us-in manual 2026-05-27-in-snap-manual
sign_scope us-in manual 2026-07-13-recovery
sign_scope us-in statute 2026-07-13-recovery
sign_scope us-ks manual 2026-05-27-ks-keesm
sign_scope us-ks manual 2026-07-13-recovery
sign_scope us-ky statute 2026-07-13-recovery
sign_scope us-la manual 2026-07-13-recovery
sign_scope us-la statute 2026-07-13-recovery
sign_scope us-ma statute 2026-07-13-recovery
sign_scope us-md statute 2026-07-13-recovery
sign_scope us-me statute 2026-07-13-recovery
sign_scope us-mi manual 2026-07-13-recovery
sign_scope us-mi statute 2026-07-13-recovery
sign_scope us-mn manual 2026-05-27-mn-combined-manual
sign_scope us-mn manual 2026-07-13-recovery
sign_scope us-mn statute 2026-07-13-recovery
sign_scope us-mo manual 2026-05-27-mo-snap-manual
sign_scope us-mo manual 2026-07-13-recovery
sign_scope us-mt regulation 2026-07-13-recovery
sign_scope us-mt statute 2026-07-13-recovery
sign_scope us-nc manual 2026-05-27-nc-fns-manuals
sign_scope us-nc manual 2026-07-13-recovery
sign_scope us-nc statute 2026-07-13-recovery
sign_scope us-nd statute 2026-07-13-recovery
sign_scope us-ne statute 2026-07-13-recovery
sign_scope us-nh regulation 2026-05-27-nh-he-w-700-snap-rules
sign_scope us-nh regulation 2026-07-13-recovery
sign_scope us-nj regulation 2026-07-13-recovery
sign_scope us-nj statute 2026-07-13-recovery
sign_scope us-nm statute 2026-07-13-recovery
sign_scope us-nv manual 2026-05-27-nv-eligibility-payments-manual
sign_scope us-nv manual 2026-07-13-recovery
sign_scope us-ny form 2026-06-05-ny-tax-current-forms
sign_scope us-ny form 2026-07-13-recovery
sign_scope us-ny statute 2026-07-13-recovery
sign_scope us-oh statute 2026-07-13-recovery
sign_scope us-or statute 2026-07-13-recovery
sign_scope us-ri statute 2026-07-13-recovery
sign_scope us-sc manual 2026-05-27-sc-snap-manual-r2026-07-15b
sign_scope us-sc manual 2026-07-13-recovery
sign_scope us-sc regulation 2026-05-29
sign_scope us-sc regulation 2026-07-13-recovery
sign_scope us-sc statute 2026-07-13-recovery
sign_scope us-tn manual 2026-05-27-tn-snap-policies
sign_scope us-tn manual 2026-07-13-recovery
sign_scope us-tn regulation 2026-05-29
sign_scope us-tn regulation 2026-07-13-recovery
sign_scope us-tx manual 2026-05-27-tx-manuals
sign_scope us-tx manual 2026-07-13-recovery
sign_scope us-ut manual 2026-05-27-ut-manuals
sign_scope us-ut manual 2026-07-13-recovery
sign_scope us-ut statute 2026-07-13-recovery
sign_scope us-va statute 2026-07-13-recovery
sign_scope us-wa statute 2026-07-13-recovery
sign_scope us-wv statute 2026-07-13-recovery
sign_scope us-wy manual 2026-05-27-wy-manuals
sign_scope us-wy manual 2026-07-13-recovery
```

After reviewing and committing all signed ingest manifests, set the immutable
release name and perform the runbook's local dry run:

```bash
export RELEASE='us-rulespec-2026-07-13'
: "${RELEASE:?missing release name}"
test -z "$(git status --porcelain)"
test -f "manifests/releases/${RELEASE}.json"
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publish_corpus.py \
  --release "$RELEASE" \
  --repo-root . \
  --base data/corpus \
  --dry-run \
  --output "/tmp/${RELEASE}-dry-run.json"
```

At the production boundary, load and validate every credential required by
`SIGNING-RUNBOOK.md`, then let the controller sign, verify, publish, and activate
the release:

```bash
: "${AXIOM_CORPUS_RELEASE_PRIVATE_KEY:?missing private release signing key}"
: "${AXIOM_CORPUS_RELEASE_PUBLIC_KEY:?missing independent public verification key}"
: "${SUPABASE_ACCESS_TOKEN:?missing Supabase management token}"
: "${R2_ACCESS_KEY_ID:?missing R2 access key id}"
: "${R2_SECRET_ACCESS_KEY:?missing R2 secret access key}"
test -z "$(git status --porcelain)"
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publish_corpus.py \
  --release "$RELEASE" \
  --repo-root . \
  --base data/corpus \
  --output "/tmp/${RELEASE}-signed-release.json"
```
