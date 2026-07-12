# Named Release Publication

Corpus artifacts may be merged without becoming public. Production visibility
changes only through one immutable named-release publication boundary.

## Contract

A tracked file under `manifests/releases/<name>.json` is a cut plan, not a
published release. It must have an explicit immutable name and exact
`jurisdiction × document_class × version` scopes. The name `current` is
reserved and rejected. Names are at most 128 characters and contain only
lowercase alphanumeric segments separated by single hyphens.

Publication accepts only the canonical, non-symlink selector path
`manifests/releases/<name>.json` from a clean Git checkout. The selector and
every selected artifact must already be tracked and committed. The commit and
its commit timestamp become signed provenance; an operator-supplied timestamp
cannot replace that checkout identity.

The publication controller derives a release object containing:

- the selector digest and source git commit;
- every selected inventory, provision, coverage, and source artifact's
  canonical local path, bytes, and SHA-256;
- content-addressed R2 keys under `objects/sha256/`;
- exact provision and derived navigation row counts plus canonical projection
  digests for every scope;
- local deep-validation, R2 readback, and pre-sign Supabase projection
  evidence; and
- an Ed25519 signature verifiable with `AXIOM_CORPUS_RELEASE_PUBLIC_KEY`.

Deep validation requires each inventory source reference to use the exact
`sources/<jurisdiction>/<document_class>/<version>/...` boundary, name a
non-symlink regular file, and include its matching SHA-256. Every provision
source reference must use that same boundary and occur in the inventory. The
signed artifact list is the complete allowed inventory for the declared
scopes; a consumer must not discover additional files by scanning a directory.

The release object's `content_sha256` addresses its signed content. R2 stores
it at `releases/<name>/<content_sha256>.json`. Reusing a name for different
content is an error.

## Publication order

`scripts/publish_corpus.py --release <selector>` performs these steps and stops
at the first failure:

1. Deep-validate all local artifacts as a no-write preflight.
2. Snapshot each artifact once, hash that snapshot, and conditionally write it
   to its SHA-256 R2 key with `If-None-Match: *`. A concurrent `409` or `412`
   converges only when readback proves the existing bytes are identical.
3. Download every selected R2 object and verify its exact bytes and hash.
4. Query prior signed objects for the selected scopes. The controller verifies
   each object with the trusted Ed25519 public key. An already released scope
   is reused only when its signed artifacts, row counts, and projection digests
   exactly match; otherwise publication stops.
5. Stage versioned provision and navigation rows for unreleased scopes. Loading
   never changes public visibility and never synthesizes missing parents.
6. Query direct base-table evidence before signing. Exact provision/navigation
   counts and canonical digests of every publisher-controlled projection field
   must match the locally derived evidence.
7. Rerun deep validation, prove the artifact and scope identity did not change,
   then build and Ed25519-sign the attested release object. The independently
   configured public key must verify it locally.
8. Conditionally write the signed object to
   `releases/<name>/<content_sha256>.json`, read it back, and verify its bytes,
   content address, schema, evidence, and signature.
9. After another local signature verification, use the Supabase Management API
   to call `corpus.activate_corpus_release`. The staging `service_role` is
   explicitly forbidden from executing this RPC. The transaction locks the
   projection tables, repeats exact counts and digests, installs immutable
   scope membership, moves the singleton production pointer, and refreshes
   `current_provision_counts`. Any error rolls the transaction back.

Partial staging is inert and safe to inspect or retry. There is no per-scope
`publish`, mutable `current.json`, publish-on-load, best-effort refresh, or
ambient release selection.

Provision staging is idempotent against verified pre-staged state. Before any
write, every loaded scope's existing rows are fetched and compared: rows that
are byte-identical across every projected column are left untouched, rows
whose release content matches but whose derived `id`/`parent_id` reflect a
superseded id scheme are converged to the canonical projection, and any
divergent content under the same immutable `(citation_path, version)` key —
or staged rows the load does not describe — aborts the load before anything
is written. An earlier ingest of the same artifacts therefore never blocks a
publish, while drifted or unexplained staged state always fails loudly
instead of being overwritten or skipped.

An exact retry is a no-op at every immutable boundary: existing R2 bytes are
verified and reused, already released scopes skip database writes, the same
release object is accepted, and an already matching production pointer is not
rewritten. A release name with different content, or a successor release that
tries to change a previously released scope, is rejected. A successor may
reuse a scope only when the prior signed scope identity is byte-for-byte equal.

## Downstream resolution

The canonical locator is
`releases/<name>/<content_sha256>.json`, produced by
`axiom_corpus.release.release_object_r2_key`. A consumer must load that v2
object, call `axiom_corpus.release.verify_release_object` with the configured
public key, and derive its allowed artifact inventory only from the verified
`content.artifacts` entries. It must persist `content_sha256` as release
identity. `selector_sha256` is signed provenance for the cut plan; it is not a
release identity and must not authorize a directory scan.

Activated named objects remain publicly readable from
`corpus.release_objects` even after the production pointer moves elsewhere;
only provision/navigation visibility follows the pointer. This preserves
historical evaluation reproducibility without reviving a mutable alias.

## Commands

Local preflight without external writes:

```bash
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/nz-rulespec-2026-07-10.json \
  --dry-run
```

Production publication requires R2 credentials, a Supabase staging credential,
a distinct Supabase Management API access token, and the release
private/public key pair. The staging credential can load rows and read evidence
but cannot activate a release. CI supplies these values; operators should not
print or persist them.

Verify a downloaded release object using only the public key:

```bash
AXIOM_CORPUS_RELEASE_PUBLIC_KEY=... \
uv run axiom-corpus-release path/to/release-object.json \
  --repo-root .
```
