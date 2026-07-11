# Corpus Ingestion Manifest Plan

Corpus artifacts should be treated as generated outputs. Agents should not type
or tune rows under `data/corpus/provisions` by hand to make a RuleSpec validator
pass.

## Contract

Every reviewed corpus ingestion scope should have a signed ingest manifest that
records:

- the `axiom-corpus` package version and git commit,
- the repository-relative root `.`, a full commit hash, and
  `dirty_tracked: false` for the generator state,
- the command or run description that produced the artifacts,
- the jurisdiction, document class, and version,
- coverage summary fields when a coverage artifact exists,
- SHA-256 hashes for generated source, inventory, provision, and coverage files,
- optional reasoning or run log files with SHA-256 hashes, and
- an Ed25519 signature from `AXIOM_CORPUS_INGEST_PRIVATE_KEY`.

The first implementation provides:

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... axiom-corpus-ingest sign-ingest-manifest \
  --jurisdiction uk \
  --document-class regulation \
  --version 2026-06-03-uk-universal-credit \
  --command "axiom-corpus-ingest extract-uk-legislation ..."
```

For intentional artifact removals, include deleted paths explicitly:

```bash
AXIOM_CORPUS_INGEST_PRIVATE_KEY=... axiom-corpus-ingest sign-ingest-manifest \
  --jurisdiction uk \
  --document-class regulation \
  --version 2026-06-03-uk-universal-credit \
  --deleted-file data/corpus/provisions/uk/regulation/obsolete.jsonl \
  --command "axiom-corpus-ingest remove-obsolete-scope ..."
```

and a CI-facing guard:

```bash
AXIOM_CORPUS_INGEST_PUBLIC_KEY=... axiom-corpus-ingest guard-ingested \
  --base-ref "$BASE_REF" \
  --head-ref "$HEAD_SHA"
```

`guard-ingested` protects `data/corpus/sources`, `data/corpus/inventory`,
`data/corpus/provisions`, and `data/corpus/coverage`. A changed file under one
of those directories must appear in a valid signed manifest whose recorded hash
matches the changed artifact bytes. The CI workflow runs the guard on pull
requests and pushes; the guard uses `git diff --no-renames` so moves out of a
protected corpus path are checked as protected deletions. Pull-request CI uses
only the public key, and after this guard lands it installs the verifier from
the base commit before checking the pull-request workspace. When `--base-ref`
is supplied, the guard reads signed manifests and protected artifact bytes from
the committed `--head-ref` tree, not from mutable files in the checkout. The
manifest's attested generator commit must be an ancestor of that guarded head.

Build and sign only from a checkout with no staged or unstaged tracked changes;
untracked generated outputs are allowed. Only a newly generated manifest with
this clean, repository-relative provenance can authorize a protected change.
Legacy manifests with absolute checkout roots, dirty generator state, or
abbreviated commits remain historical files but are rejected if a changed
artifact tries to rely on them. Do not edit their provenance fields or re-sign
them as if they had been clean; rerun the generator from a clean commit instead.

## Migration Steps

1. Use `sign-ingest-manifest` for new corpus artifact PRs.
2. Add extractor-native `--write-manifest` support so each `extract-*` command
   writes the manifest automatically after successful coverage.
3. Record structured reasoning logs from agent runs and include them through
   `--reasoning-log`.
4. Backfill manifests for active current-release scopes before enabling broad
   `--all` style release validation.

This keeps RuleSpec repos dependent on ingested corpus artifacts rather than
local source snippets, matching the `axiom-encode --apply` model for generated
encodings.
