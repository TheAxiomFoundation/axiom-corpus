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
   Steps 2 and 3 run per object on a bounded thread pool
   (`publish_corpus.py --r2-workers`, default 16); the pool changes only how
   many objects are in flight, never what is verified, and the first failure
   stops staging. The signed readback evidence lists keys in artifact order
   regardless of completion order.
4. Query prior signed objects for the selected scopes. The controller verifies
   each object with the current Ed25519 public key or an explicitly configured
   legacy verification key. An already released scope is reused only when its
   signed artifacts, row counts, and projection digests exactly match;
   otherwise publication stops.
5. Stage versioned provision and navigation rows for unreleased scopes. Loading
   never changes public visibility and never synthesizes missing parents.
6. Query direct base-table evidence before signing. Exact provision/navigation
   counts and canonical digests of every publisher-controlled projection field
   must match the locally derived evidence. The evidence RPC is per scope,
   so the controller requests it in chunks of 32 scopes and splits a chunk
   the gateway rejects (a 504 after it ran too long) in half until it fits;
   every selected scope must still appear exactly once across all chunks.
7. Rerun deep validation, prove the artifact and scope identity did not change,
   then build and Ed25519-sign the attested release object. The independently
   configured public key must verify it locally.
8. Conditionally write the signed object to
   `releases/<name>/<content_sha256>.json`, read it back, and verify its bytes,
   content address, schema, evidence, and signature.
Publication ends here: the release is signed and durable, but serving is
unchanged.

Key rotation must preserve the retiring public key before replacing the current
pair. Set `AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS` to a JSON array of retired
public keys, then rotate `AXIOM_CORPUS_RELEASE_PRIVATE_KEY` and
`AXIOM_CORPUS_RELEASE_PUBLIC_KEY` together. Legacy keys authenticate only prior
immutable release objects during safe scope reuse. Newly published objects,
R2 readback, and activation must verify with the current public key. Keep every
retired key needed by a release that can supply an already published scope.

9. Activation is a separate, deliberate step (`scripts/activate_release.py`, or
   `publish_corpus.py --activate`), because it moves serving and can displace
   another jurisdiction's release (axiom-corpus#408). After another local
   signature verification it sends compact signed scope evidence for preview.
   After protected approval, the canonical release object is uploaded through a
   private bounded-chunk transport; PostgreSQL verifies the reconstructed object
   hash and identity before calling `corpus.activate_corpus_release`. The staging
   `service_role` is explicitly forbidden from reading the upload or executing
   this RPC. The transaction locks the projection
   tables (and takes an EXCLUSIVE lock on `active_scope_pointer` to serialize
   activations), repeats exact counts and digests, installs immutable scope
   membership, then repoints the per-`(jurisdiction, document_class)` serving map
   for only the pairs this release carries — recording each takeover in
   `corpus.scope_activation_history` — and refreshes `current_provision_counts`.
   Any error rolls the transaction back. Preview the takeover first with
   `activate_release.py --dry-run`.

Publication retains the exact signed release object as a 30-day GitHub Actions
artifact. When production credentials are available only to GitHub Actions,
dispatch `activate-release.yml` with that publication run ID, immutable release
name, and content SHA-256. The `release-preview` environment is restricted to
the default branch. When activation is requested, the mutation job waits for
approval in the protected `release-activation` environment after the preview
job summary is available. The approved job downloads the same publication
artifact, re-verifies its identity and signature, and reruns the takeover
preview immediately before installing the idempotent private upload schema and
running the transactional activation RPC.

Publication writes one flushed, timestamped progress line to stderr at the
start and end of every phase (deep validation, release content, R2 staging,
released-scope lookup, provision and navigation staging, staged evidence,
signing, release-object upload) with object, scope, and row counts and
elapsed seconds, and names the phase on failure. These lines are operational
logging only and never enter signed content.

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
publish, and drifted or unexplained staged state fails the load instead of
being overwritten or skipped.

Staging verification and its writes are separate REST requests, not one
transaction; the operating assumption is a single staging writer at a time.
Concurrent-writer races are narrowed rather than eliminated: replacements
re-check the ON DELETE CASCADE dependent set immediately before deleting,
in-place converges write only `parent_id` conditioned on the verified prior
value, and inserts carry no conflict resolution so any surviving collision is
a database error. Rows already inside a signed release are protected
server-side by the released-scope trigger regardless of client behavior, and
publication's evidence gate re-derives every in-release scope's counts and
projection digests after staging. The signed activation RPC remains the only
transactional boundary.

An exact retry is a no-op at every immutable boundary: existing R2 bytes are
verified and reused, already released scopes skip database writes, the same
release object is accepted, and an already matching production pointer is not
rewritten. A release name with different content, or a successor release that
tries to change a previously released scope, is rejected. A successor may
reuse a scope only when the prior signed scope identity is byte-for-byte equal.

Publication memory grows with the release's row count, not its bytes. Every
phase streams a provisions file one row at a time and keeps compact per-row
metadata (identity, parent, source path, dates, row digests), not provision
bodies: deep validation and the signed-source-reference check read rows as
they parse; release content hashes the provisions artifact into a temporary
snapshot, then parses and projects that verified copy in one pass; staging
parks projected rows in a temporary file and reads each back only to compare
it with a staged row or to insert it; and R2 objects are verified in 1 MB
reads. Bodies are still held briefly in bounded batches: a page of up to 1,000
staged rows while it is compared, a chunk of up to 500 rows (the default
chunk size) while it is inserted, and a whole file only on an error path that
reproduces the old reader's error. The cross-scope checks (the release's citation-path set and
staging's key map) keep one compact entry per row across every scope they
cover. The streaming readers return the same records and raise the same
errors as the whole-file readers they replace, with one exception: JSON nested
within a few levels of the parser's recursion limit (about 52,000 levels) can
get a different outcome. A streaming reader may raise `RecursionError` on a
file the old reader accepted, or accept a file the old reader rejected with
`RecursionError`. No artifact nests that deep.
`tests/test_streaming_*.py` hold the streaming code to the pre-streaming
implementations, mostly on Hypothesis-generated inputs.

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

## Layered scopes

A release may serve a base scope underneath its primary scopes: a whole-Code
base published once and reused unchanged by every successor, with newly
encoded sections layered over it. Precedence is per
`(jurisdiction, document_class)` pair: for a citation path both layers of a
pair carry, serving picks the primary row, whatever the versions' dates or the
scopes' order; every other base row is served.

**Selectors.** A scope may carry `"layer": "base"`. A primary scope has no
`layer` key; an explicit `"primary"` or any other value is rejected, so each
scope has one encoding and historical selectors and signed scope dictionaries
keep their bytes. A release carries at most one base scope per pair.
Validation keeps citation paths unique within each layer and accepts a
base/primary overlap only inside one pair. Parent closure stays per scope: a
row's parent id is derived from the parent's path and the row's own version,
so a primary section whose title is only in the base declares no parent, and
serving places it under the base title. Validation merges each layered
pair's trees as serving does and warns (it does not fail) when a primary root
lands under no served ancestor, so a mistyped path would become a new
top-level document (`layered_primary_root_unattached`), and when the two layers
disagree about which of two paths is the ancestor, so serving breaks a parent
cycle (`layered_parent_cycle_broken`). A base scope's artifacts may be pinned
by a committed corpus lock rather than tracked in git
(`docs/corpus-storage.md`).

**Release objects.** A release without a base scope signs
`axiom-corpus/release-object/v3`, byte for byte as before
(`tests/fixtures/release_layers/pre_layer_v3_release.json`). One with a base
scope signs `axiom-corpus/release-object/v4`: v3 plus `"layer": "base"` on base
scope entries, covered by `selector_sha256`. Verification rejects a v4 object
without a base scope and a v2 or v3 object with a layer anywhere. A scope's
signed dictionary includes its layer, so a version released in one layer
cannot be reused in the other.

**Registration** (`corpus.stage_corpus_release_object`) accepts v4 from
`supabase/migrations/20260927100000_stage_signed_release_object_v4.sql`, which
`scripts/apply_release_object_staging_migration.py` applies on every publish
and register-release-object run; v2 and v3 objects register exactly as before.

**Serving** needs `supabase/migrations/20260927110000_layered_release_serving.sql`,
which no workflow applies; until it is applied, activation rejects every v4
object. It records each scope's signed layer in `corpus.release_scopes.layer`
(historical rows are primary) and, whenever a pair's serving release changes,
derives two tables in the same transaction (a trigger on
`corpus.active_scope_pointer`):

- `corpus.layered_shadowed_rows`: the base provision and navigation rows a
  primary row of the pair shadows. `current_provisions` and the
  `navigation_nodes` read policies exclude them; `legacy_provisions` includes
  them.
- `corpus.layered_navigation_overrides`: the merged tree. A primary node keeps
  the parent its own scope gives it; a node that is a root of its scope takes
  its base twin's parent, or the nearest served ancestor path when the base
  does not carry its path; depth, child and encoded-descendant counts are
  recomputed. `current_navigation_nodes` serves these rows in place of the
  stored ones. A direct `navigation_nodes` read returns the stored per-scope
  tree fields, so tree browsing should read `current_navigation_nodes`.

Both tables are empty for a pair served without a base scope, so serving is
then exactly what it was. Served counts (`current_provision_counts`,
`get_root_document_counts()`) count winners; a scope's signed and staged row
count still includes its shadowed base rows. `get_root_document_counts()`
counts served roots only, as open PR #666 defined it; the repository's earlier
`20260910120000` counted every stored root, superseded and unreleased versions
included.

The derived tables stay a function of what is served, whoever writes, short
of an owner bypassing the guards (turning triggers off with
`session_replication_role = replica`, or setting
`corpus.layered_serving_derivation` or a `corpus.layered_base_pairs_*`
setting by hand):

- Any change to `corpus.active_scope_pointer` that moves a pair to or from a
  release with a base scope for it re-derives the pair, and so does any move
  of a pair that still has derived rows (left behind by membership altered
  with triggers off). The pointer trigger
  takes no further lock on `active_scope_pointer`: the row lock of the write
  orders it against other writes of the same pair. When it derives, it writes
  the two derived tables and analyzes them, which holds `SHARE UPDATE
  EXCLUSIVE` on both until commit, so owner writes that move two layered
  pairs at once wait for each other and can deadlock (one rolls back).
  Activations take `EXCLUSIVE` on the pointers and so run one at a time.
- Membership of a signed release is immutable. An `UPDATE`, `DELETE` or
  `TRUNCATE` of `corpus.release_scopes` is rejected, and an inserted row must
  be one of its release object's signed scopes, with its signed layer (checked
  once per statement). A signed scope that joins a pair its release already
  serves (membership altered before this guard and restored) re-derives that
  pair in the same statement. A statement inserting any row whose release
  signs a base scope for that row's pair (decided from the signed object, read
  once per release per statement) takes `EXCLUSIVE` on `active_scope_pointer`
  (activation already holds it; an owner restoring a row takes it); any other
  insert takes no lock.
- A signed release object is immutable too: only its `created_at` may change,
  and an object with membership cannot be deleted, so no statement can hide it
  from the membership and released-row guards.
- `TRUNCATE` of `provisions` or `navigation_nodes` is rejected while either
  holds a row of a signed release's scope, as row writes already are.
- The derived tables are written only by the derivation: any other write is
  rejected.
- A direct `SELECT corpus.refresh_layered_serving(...)` takes `EXCLUSIVE` on
  `active_scope_pointer` before it reads anything, so it cannot interleave
  with a pointer write, an activation or a re-derivation. Run it in a
  transaction of its own: one that has already written a pointer holds `ROW
  EXCLUSIVE`, and two such transactions asking for `EXCLUSIVE` deadlock (a
  pointer write re-derives its pair anyway).
- `SELECT corpus.rederive_layered_serving()` re-derives every served pair.

**Isolation.** Writes that involve no release with a base scope for the pair
they touch derive nothing, so activating, re-activating or rolling back a
v2 or v3 release, a hand repoint or removal of a pointer between such
releases, and inserting their membership work under any isolation level, as
before. Moving a pair to or from a release with a base scope for it, by
activation or by hand, and inserting membership rows of such a release for
such a pair, run only under `READ COMMITTED` and are refused whole otherwise:
a `REPEATABLE READ` or `SERIALIZABLE` snapshot taken before another session's
write committed would derive from rows it cannot see. (Re-activating the
layered release that already serves every one of its pairs moves nothing and
inserts nothing, so it works under any level.) So do `rederive` and a direct
`refresh`. `TRUNCATE` of `active_scope_pointer`, `release_scopes`,
`provisions` or `navigation_nodes` also runs only under `READ COMMITTED`,
layered or not: `TRUNCATE` removes rows its own snapshot cannot see, so its
guards must read a fresh one. `READ UNCOMMITTED`, which PostgreSQL runs as
`READ COMMITTED`, counts as `READ COMMITTED` throughout.

The July row guard (`guard_released_scope_row_immutable`, `20260710180000`),
which this file does not change, still decides from the writer's snapshot: a
`REPEATABLE READ` or `SERIALIZABLE` row write whose snapshot predates an
activation can change rows that activation released. Nothing in this
repository writes staged rows under those levels (PostgREST and the scripts
use the server default); closing it would refuse such writes outright, which
depends on how production writers are configured.

Each derivation that changes the derived tables runs `ANALYZE` on both.
Staged rows do not keep a provision's citation label, so where the merge moves
a node that has no heading and whose citation label equals its old segment,
the served label follows the new segment while `build_navigation_nodes` would
keep the citation label. That label is the only known difference.

`SupabaseQuery.get_section_with_children` returns, for a pair served without a
base scope, the `parent_id` children it always returned. For a layered pair, a
served title's sections may be base rows whose `parent_id` names the base
title, so it reads the served navigation tree, paging past PostgREST's row cap,
and keeps one child per path.

### Deploying the serving migration

Apply `20260927110000` by hand, as `postgres`, at a time of low traffic:

1. Build the two `navigation_nodes` indexes of section 1 of the file with
   `CREATE INDEX CONCURRENTLY IF NOT EXISTS` and their exact definitions, then
   confirm `pg_index.indisvalid` for both. The file refuses to run over an
   invalid one.
2. Apply the file in one transaction, with no publication or activation
   running:

   ```bash
   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
     -f supabase/migrations/20260927110000_layered_release_serving.sql
   ```

   Without `--single-transaction`, psql commits each statement on its own, and
   neither the lock order below nor the roll-back on failure holds. The file
   first takes a transaction-level advisory lock, so a second application waits
   for the first. Section 1 takes `SHARE` on `navigation_nodes`, which reads do
   not wait for. Next it takes `SHARE ROW EXCLUSIVE`, which writes wait for and
   reads do not, on `provisions`, `navigation_nodes`, `active_scope_pointer`,
   `release_objects`, `release_scopes` and (when re-applied) the two derived
   tables, in the order activation takes its locks, so that a write in progress
   delays the file before it holds anything a read waits for. Then it takes
   `ACCESS EXCLUSIVE` on the four serving views it replaces, `navigation_nodes`
   (its read policies) and `release_scopes` (the new column), in the order
   serving reads take their locks: `current_provisions`, `legacy_provisions`,
   `current_navigation_nodes`, `navigation_nodes`, `current_release_scopes`,
   `release_scopes`. It holds them until it commits, and the first time also
   holds the two derived tables it creates, which no read can reach yet. After
   those it waits for no lock. The file does no derivation work, so the
   transaction is short: on an otherwise idle local PostgreSQL 14 copy of
   401,299 rows per table, its indexes already built, a re-application took 8
   ms, and a first application of a small database 11 ms. These are one-off
   measurements, not part of the test suite, of the file before its last
   change, which added one statement that only takes locks.

   What a concurrent read sees. A read here is one statement, as every
   PostgREST request and RPC call is. A read that got its locks before the file
   got the one it needs runs with the old definitions, and the file waits for
   it; a read that needs a relation the file holds, or is queued for, waits
   until the file commits and then runs with the new definitions (or, if the
   file rolled back, the old ones). Because the file takes its locks in the
   readers' order, a read and the file never deadlock. A read can still fail if
   the file holds it past the read's own statement timeout (Supabase gives anon
   3 s by default): the file can wait up to 2 s for each of its six `ACCESS
   EXCLUSIVE` locks in turn while reads queue behind the ones it holds. A
   transaction that reads one relation and then another in a later statement is
   outside that guarantee and can deadlock with the file, which then rolls
   back. In a local PostgreSQL 14 run, applying the file 40 times in a row
   under 12 looping anon readers deadlocked no read and no application, where
   the previous file deadlocked 40 of 40 re-applications;
   `test_applying_the_file_under_looping_serving_reads_deadlocks_nothing` runs
   a shorter loop of the same kind, and the lock-order tests check both orders.

   The file sets `lock_timeout` to 2 s, so each lock it waits for is waited
   for at most 2 s. A failed run (a lock timeout, or any other error) rolls
   the whole transaction back and changes nothing: wait for a quieter moment
   and run it again.
3. The first time, no base scope is served: the file empties the derived
   tables and every view returns what it returned before. When a base scope is
   served (re-applying the file after a layered activation), it prints a notice
   and leaves the derived state as the triggers kept it. Then run
   `SELECT corpus.rederive_layered_serving();` as its own transaction, under
   `READ COMMITTED`. It takes the locks activation takes and no other:
   `EXCLUSIVE` on `active_scope_pointer` (which blocks activations and pointer
   writes, not reads), and row writes and `ANALYZE` on the two derived tables.
   Only when the shadowed provisions change does it also refresh
   `current_provision_counts`, as activation does; count reads wait for that
   refresh. Serving reads see the previous state until it commits. It took
   2.9 s on the 401,299-row copy and 7.3 s for the derivation at 1.52M rows.

## Commands

Local preflight without external writes:

```bash
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/nz-rulespec-2026-07-10.json \
  --dry-run
```

Production publication requires R2 credentials, a Supabase staging credential,
a distinct Supabase Management API access token, and the release
private/public key pair. After a key rotation, publication also requires the
JSON-array legacy public-key variable described above. The staging credential
can load rows and read evidence but cannot activate a release. CI supplies these
values; operators should not print or persist private credentials.

Verify a downloaded release object using only the public key:

```bash
AXIOM_CORPUS_RELEASE_PUBLIC_KEY=... \
uv run axiom-corpus-release path/to/release-object.json \
  --repo-root .
```

Preview and then activate through the protected workflow boundary:

```bash
gh workflow run activate-release.yml \
  -f publish_run_id=<publish-run-id> \
  -f release=us-rulespec-2026-07-19-dedup \
  -f content_sha=<sha256> \
  -f request_activation=false

gh workflow run activate-release.yml \
  -f publish_run_id=<publish-run-id> \
  -f release=us-rulespec-2026-07-19-dedup \
  -f content_sha=<sha256> \
  -f request_activation=true
```

For the second command, inspect the completed preview job summary before
approving the waiting `release-activation` deployment.
