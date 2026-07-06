# 2026-07-05 Sign Canada (ca) policy ingest manifests

## Context

axiom-corpus PR #155 (`codex/canada-2026-tax-corpus`) carries 97 Canada
policy grounding scopes (CRA T1 2025, T4127 2026, TD1, Quebec TP-1
schedules, ESDC benefits). The branch is rebased on main, renamed from
`canada/...` to `ca/...` per the citation-path schema, record ids are
normalized to the versioned uuid5 identity, and the A6 grammar check
passes. The only remaining failure is `guard-ingested`: these scopes
were produced by a codex session without the ingest signing key, so no
`.axiom/ingest-manifests/ca/` manifests exist yet.

This needs a key-holder. Run the loop below wherever
`AXIOM_CORPUS_INGEST_PRIVATE_KEY` is available.

## Command

```bash
git fetch origin
git checkout codex/canada-2026-tax-corpus
git pull --ff-only

for f in data/corpus/provisions/ca/policy/*.jsonl; do
  version=$(basename "$f" .jsonl)
  uv run --extra dev axiom-corpus-ingest sign-ingest-manifest \
    --jurisdiction ca \
    --document-class policy \
    --version "$version" \
    --command "codex canada-2026-tax-corpus grounding; canada->ca rename and id normalization applied on top (PR #155)"
done

git add .axiom/ingest-manifests
git commit -m "Sign ca policy ingest manifests"
git push
```

CI's `guard-ingested` step verifies the signatures against the repo's
`AXIOM_CORPUS_INGEST_PUBLIC_KEY` variable on the next run.

## After this

1. PR #155 goes green -> mark ready and merge.
2. rulespec-ca PR #3 (encodings, already apply-manifest-signed) re-runs
   validation, resolves all `ca/...` citations against corpus main ->
   merge.
3. Canada appears on axiom-foundation.org/encoded automatically (the
   frontend already ships `ca` support).
