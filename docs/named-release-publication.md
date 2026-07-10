# Named Release Publication

Corpus artifacts may be merged without becoming public. Production visibility
changes only through one immutable named-release publication boundary.

## Contract

A tracked file under `manifests/releases/<name>.json` is a cut plan, not a
published release. It must have an explicit immutable name and exact
`jurisdiction × document_class × version` scopes. The name `current` is
reserved and rejected. Names are at most 128 characters and contain only
lowercase alphanumeric segments separated by single hyphens.

The publication controller derives a release object containing:

- the selector digest and source git commit;
- every selected artifact's canonical local path, bytes, and SHA-256;
- content-addressed R2 keys under `objects/sha256/`;
- exact provision and derived navigation rows for every scope;
- local deep-validation, R2 readback, and Supabase count attestations; and
- an Ed25519 signature verifiable with `AXIOM_CORPUS_RELEASE_PUBLIC_KEY`.

Publication requires an exact Git checkout identity even when the caller
supplies an explicit creation timestamp; a timestamp never substitutes for
source provenance.

The release object's `content_sha256` addresses its signed content. R2 stores
it at `releases/<name>/<content_sha256>.json`. Reusing a name for different
content is an error.

## Publication order

`scripts/publish_corpus.py --release <selector>` performs these steps and stops
at the first failure:

1. Deep-validate all local artifacts as a no-write preflight.
2. Upload missing artifacts to their SHA-256 R2 keys.
3. Download every selected R2 object and verify its exact bytes and hash.
4. Stage versioned provision and navigation rows. Loading never changes public
   visibility and never synthesizes missing parents.
5. Query direct, exact per-version provision and navigation row counts and
   compare both with the hashed JSONL row count.
6. Rerun deep validation, then build and Ed25519-sign the attested release
   object. The configured public key must verify it.
7. Upload, download, and verify the signed release object.
8. Call `corpus.activate_corpus_release` once. The RPC repeats exact counts,
   installs immutable membership, moves the singleton production pointer, and
   refreshes `current_provision_counts` in one transaction. A count or refresh
   error rolls the pointer change back.

Partial staging is inert and safe to inspect or retry. There is no per-scope
`publish`, mutable `current.json`, publish-on-load, best-effort refresh, or
ambient release selection.

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

Production publication requires R2 credentials, a Supabase service credential,
and the release private/public key pair. CI supplies those values; operators
should not print or persist them.

Verify a downloaded release object using only the public key:

```bash
AXIOM_CORPUS_RELEASE_PUBLIC_KEY=... \
uv run axiom-corpus-release path/to/release-object.json \
  --repo-root .
```
