# US recovery signing runbook

This runbook stops before publication unless the recovery report accounts for all
711 planned citations and every remainder is an explicit documented exclusion.
Run it from the repository root on the reviewed signing commit. Publication is a
networked production operation and is intentionally not part of recovery generation.

## 1. Verify the reviewed checkout

```bash
git switch recovery/us-ingested-batch1
test -z "$(git status --porcelain)"
test "$(jq -r '._summary.targets' recovered-coverage-report.json)" = 711
test "$(jq -r '._summary.signing_checklist.ready_to_sign' recovered-coverage-report.json)" = true
jq -e '._summary.signing_checklist
  | .all_711_planned_citations_accounted_for
    and .all_exclusions_have_citations_reasons_and_tracking
    and .all_fetched_files_have_valid_provenance
    and .all_parsed_scopes_have_complete_coverage
    and .parse_failures_reviewed' recovered-coverage-report.json >/dev/null
```

Run the repository gates against that exact clean commit:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports
UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev python -m pytest -q
UV_CACHE_DIR=/tmp/uv-cache uv run --extra dev towncrier check
```

## 2. Select and dry-run the immutable release

Set `RELEASE` to the reviewed canonical selector basename. The guard rejects a
missing or non-canonical selector.

```bash
export RELEASE='REPLACE_WITH_REVIEWED_RELEASE_NAME'
: "${RELEASE:?set RELEASE to the reviewed immutable release name}"
test -f "manifests/releases/${RELEASE}.json"
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publish_corpus.py \
  --release "$RELEASE" \
  --repo-root . \
  --base data/corpus \
  --dry-run \
  --output "/tmp/${RELEASE}-dry-run.json"
```

The dry run performs deep local validation but does not upload, stage database
rows, sign, or activate the release.

## 3. Load publication credentials without writing them to the repository

After corpus #329, signing requires independently configured private and public
Ed25519 key material. Each value may be a 32-byte raw key encoded as base64 or a
PEM value (literal newlines or `\\n` escapes). The public key is mandatory and is
used to verify the newly signed object before upload.

```bash
export AXIOM_CORPUS_RELEASE_PRIVATE_KEY='REPLACE_WITH_PRIVATE_ED25519_KEY'
export AXIOM_CORPUS_RELEASE_PUBLIC_KEY='REPLACE_WITH_MATCHING_PUBLIC_ED25519_KEY'
export SUPABASE_ACCESS_TOKEN='REPLACE_WITH_MANAGEMENT_API_TOKEN'
export SUPABASE_SERVICE_ROLE_KEY='REPLACE_WITH_SERVICE_ROLE_KEY'
export R2_ACCESS_KEY_ID='REPLACE_WITH_R2_ACCESS_KEY_ID'
export R2_SECRET_ACCESS_KEY='REPLACE_WITH_R2_SECRET_ACCESS_KEY'
export R2_ACCOUNT_ID='REPLACE_WITH_CLOUDFLARE_ACCOUNT_ID'
export R2_BUCKET='axiom-corpus'
```

`SUPABASE_SERVICE_ROLE_KEY` may be omitted only when `SUPABASE_ACCESS_TOKEN` can
retrieve it through the Supabase Management API. R2 credentials may instead be
supplied with `--credentials-file`; do not commit that file.

Fail closed if any required signing/publication value is empty:

```bash
: "${AXIOM_CORPUS_RELEASE_PRIVATE_KEY:?missing private signing key}"
: "${AXIOM_CORPUS_RELEASE_PUBLIC_KEY:?missing independent public verification key}"
: "${SUPABASE_ACCESS_TOKEN:?missing Supabase management token}"
: "${R2_ACCESS_KEY_ID:?missing R2 access key id}"
: "${R2_SECRET_ACCESS_KEY:?missing R2 secret access key}"
```

## 4. Publish, sign, and verify (does not move serving)

This is the production publication boundary. The controller deep-validates locally,
uploads and reads back content-addressed R2 artifacts, stages and verifies exact
Supabase provision/navigation projections, and signs and public-key-verifies the
release object. It does NOT activate: serving is unchanged.

```bash
test -z "$(git status --porcelain)"
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/publish_corpus.py \
  --release "$RELEASE" \
  --repo-root . \
  --base data/corpus \
  --output "/tmp/${RELEASE}-signed-release.json"
```

Retain `/tmp/${RELEASE}-signed-release.json` as the operator copy of the exact
signed release object. Any command failure means the release is not approved;
do not manually advance a pointer or bypass the controller.

## 5. Activate (move serving) — separate, deliberate step

Activation repoints the per-`(jurisdiction, document_class)` serving map and can
displace another jurisdiction's release (axiom-corpus#408), so it is decided and
run separately from publication. Always preview the takeover first.

```bash
# Preview: what would this release displace? (read-only, moves nothing)
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/activate_release.py \
  --release-object "/tmp/${RELEASE}-signed-release.json" \
  --dry-run

# Activate after reviewing every changed pair:
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/activate_release.py \
  --release-object "/tmp/${RELEASE}-signed-release.json"
```

Serving follows the per-scope map; only the pairs this release carries move, and
each takeover is recorded in `corpus.scope_activation_history`.

The protected workflow keeps the preview request bounded by sending only the
verified release name and signed scope evidence. After approval it installs the
idempotent private upload transport, sends the canonical release object in
bounded chunks, and requires PostgreSQL to verify the reconstructed object hash
and identity before entering the existing atomic activation transaction. The
private chunks are removed after activation and are never readable by public or
staging roles.
