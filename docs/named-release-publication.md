# Named Release Publication

Corpus artifacts may be merged without becoming public. Production visibility
changes only through one immutable named-release publication boundary.

## Contract

A tracked file under `manifests/releases/<name>.json` is a cut plan, not a
published release. It must have an explicit immutable name and exact
`jurisdiction × document_class × version` scopes. The name `current` is
reserved and rejected. Names are at most 128 characters and contain only
lowercase alphanumeric segments separated by single hyphens.

Merging a selector does not authorize publication. After review and green CI,
an operator must explicitly dispatch `publish.yml` with that selector's
immutable name or path. The workflow does not run on pushes to `main`.

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

Deep validation also applies the repository's release policy
([release-gate-policy.md](release-gate-policy.md)): a selector may not select a
scope listed in `manifests/withdrawn-scopes.yaml` unless that entry grandfathers
it, and a selected scope may carry only the content findings (page navigation,
chrome-prefixed bodies, hollow document roots, version pickers) that
`manifests/release-content-baseline.json` records for its exact bytes. Known
conditions are reported as notices and leave the attested error and warning
counts unchanged.

The release object's `content_sha256` addresses its signed content. R2 stores
it at `releases/<name>/<content_sha256>.json`. Reusing a name for different
content is an error.

## Publication environment setup

The `publish` job runs only for a `workflow_dispatch` on `main` and uses the
protected `release-publish` environment. The environment's deployment branch
rule is the strict boundary. The job's `if` is a first filter only: GitHub
compares strings case-insensitively, so it would also match `refs/heads/MAIN`.
Configure it in this order:

1. `release-publish` exists in the repository's GitHub Actions environment
   settings, with a deployment branch rule allowing only `main` and
   administrator bypass disabled. Required reviewers are optional.
2. The maintainer adds these three groups of environment secrets, retaining
   their existing names:

   - Release signing: `AXIOM_CORPUS_RELEASE_SIGNING_KEY`.
   - R2 access: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
     `R2_ENDPOINT`, and `R2_BUCKET`.
   - Supabase management: `SUPABASE_ACCESS_TOKEN`.

   Environment secrets take precedence over repository secrets. The workflow
   continues mapping the signing secret to `AXIOM_CORPUS_RELEASE_PRIVATE_KEY`.
   The maintainer handles the values; agents do not read or move them.
3. Only after the publication-gate PR merges, the hub deletes the
   repository-level copies of those secrets. Before deleting shared copies,
   verify that `release-mirror` retains its R2 secrets and that
   `release-preview` and `release-activation` retain their Supabase token.
   CI must also retain access to `R2_ACCOUNT_ID`, `R2_ENDPOINT`, and `R2_BUCKET`
   for read-only corpus fetches; it uses separate `R2_CORPUS_READ_*` credentials.
   CI jobs use no environment, so environment-only copies cannot supply that
   metadata: keep it as repository or organization secrets (or variables), and
   delete only the repository copies of the publication credentials.

`publish.yml` is the only workflow that reads the release signing key.
`activate-release.yml` and `register-release-object.yml` use the existing
preview/activation environments and verify signatures with public keys.
`mirror-release.yml` writes R2 objects through `release-mirror` and verifies
with a public key. CI fetches and verifies corpus objects with read-only R2
credentials. These workflows retain their existing gates.

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
counts served roots only, as `20260910140000` (#666) defines it; the earlier
`20260910120000` counted every stored root, superseded and unreleased versions
included.

The derived tables stay a function of what is served, whoever writes, short
of an owner bypassing the guards (turning triggers off with
`session_replication_role = replica`, or setting
`corpus.layered_serving_derivation` or a `corpus.layered_base_pairs_*`
setting by hand):

- Any change to `corpus.active_scope_pointer` that moves a pair to or from a
  release with a base scope for it re-derives the pair, and so does any move,
  under `READ COMMITTED`, of a pair that still has derived rows (left behind
  by membership altered with triggers off). The pointer trigger
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
   confirm `pg_index.indisvalid` for both. Copy each statement from the file
   and add only `CONCURRENTLY`. The file refuses to run over an invalid one,
   or over an index of the same name that is not on `corpus.navigation_nodes`
   or whose `pg_get_indexdef` differs from the one the file builds; it then
   rolls back whole and says which.
   Drop that index and build it again from the file's statement.
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
   reads do not, on `provisions`, `navigation_nodes`, `release_objects`,
   `release_scopes`, `active_scope_pointer` and (when re-applied) the two
   derived tables, in an order consistent with activation, membership inserts
   and derivations, so that a write in progress delays the file before it holds
   anything a read waits for. Then it takes `ACCESS EXCLUSIVE` on the four
   serving views it replaces, `navigation_nodes` (its read policies) and
   `release_scopes` (the new column), in the order serving reads take their
   locks: `current_provisions`, `legacy_provisions`,
   `current_navigation_nodes`, `navigation_nodes`, `current_release_scopes`,
   `release_scopes`. It holds them until it commits, and the first time also
   holds the two derived tables it creates, which no read can reach yet. After
   those it waits for no lock a read or a row write can hold (an owner's
   uncommitted `GRANT` on one of its objects would still make it wait, up to
   its lock timeout). The file does no derivation work, so the transaction is
   short. In one-off local measurements on PostgreSQL 14 (not part of the test
   suite), an earlier revision of the file, re-applied to an otherwise idle
   copy of 401,299 rows per table with its indexes built, took 8 ms; the
   current file, applied 20 times to the small test fixture on a busy machine,
   took a median of 12 ms re-applied and 92 ms the first time, which creates
   the derived tables and indexes.

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

### Successor cuts

A later cut of a layered line carries every base scope of its predecessor
unchanged. A shared composer builds new cuts that way. The selector lineage
check reports a cut that does not. Dedup
(`scripts/deduplicate_release_selector.py`), consolidation
(`scripts/consolidate_release_scopes.py`), composition
(`scripts/compose_scope_versions.py`), repair
(`scripts/repair_plan_cascade_self_containment.py`), the CA composite builder
(`scripts/build_ca_rulespec_composite_scope.py`), the composer
(`compose_successor`) and the signer (`scripts/sign_release_scopes.sh`) leave
alone a scope that a selector they read marks as a base, and refuse one named
as a primary scope. The threat model at the end of this section defines what
each reads: the checkouts whose committed selectors count, the selectors a run
is given, and the artifact paths it checks. Its stated limits list what lies
outside that. Other scripts that rewrite a scope in place have no layer check
yet: `scripts/self_contain_usc_scope.py`,
`scripts/slim_us_recovery_statutes.py`,
`scripts/repair_us_release_source_references.py`, `scripts/recover_ingest.py`,
`scripts/recover_ingest_batch.py` and the extract writer in
`src/axiom_corpus/corpus/usc.py`. Don't run them on a base scope; #1002
tracks their guard.

**Composing a cut.** `axiom_corpus.corpus.successors.compose_successor` builds
a successor's `ReleaseManifest` from its predecessor's. Each change names
scopes as `(jurisdiction, document_class, version)` tuples of strings:

- `add`: new primary scopes.
- `replace`: a map from a primary scope of the predecessor to a new version in
  the same pair.
- `remove`: primary scopes of the predecessor to drop.
- `add_base`: a base scope for a pair the predecessor has no base for.

Every base scope of the predecessor appears in the result as the same
`ReleaseScope`. The successor inherits the predecessor's quality profile. Its
scopes are sorted by `(jurisdiction, document_class, version)`. The composer
writes no file. It raises `SuccessorError` when a change would:

- replace or remove a base scope;
- replace or remove a scope the predecessor does not select as a primary
  scope;
- add a scope the predecessor selects, in either layer;
- replace a scope with its own version, or with a version the predecessor
  already selects;
- add a scope, or replace a scope with a version, that a tracked selector
  marks as a base (`tracked_bases`, read from `releases_dir`);
- list one scope more than once across `add`, `replace`, `remove` and
  `add_base`, or select one scope twice;
- add a base for a pair the predecessor already has a base for, or two bases
  for one pair;
- give the successor the predecessor's name, or no scope at all.

Replacing a base is a reviewed release decision, which the composer does not
make. The lineage baseline records it under `base_replacements`.

The description must name the predecessor. The lineage check takes the first
tracked selector a description names as the cut's predecessor ([Selector
lineage](release-gate-policy.md#selector-lineage)). The composer resolves the
description against the tracked selector names and the predecessor's, as the
check does, and refuses it unless the first name it finds is the predecessor.
It reads the names from `releases_dir`, the `manifests/releases` of the
checkout the cut is committed to, and without it from the checkout the module
is imported from. A tracked selector is one committed at HEAD: when
`releases_dir` is a checkout's `manifests/releases`, the composer reads the
selectors committed there, so a file the working tree hides (a sparse checkout,
`skip-worktree`, an unstaged deletion or edit) still counts as committed, and
an untracked or only staged file does not. Any other directory, inside a
checkout or not, is read from disk as given, byte for byte, line endings kept,
unless a rule below refuses it. A `releases_dir` that is a symlink, whose parent
directory is one (such as a checkout's `manifests` linked to another
checkout's), that is spelled with `..`, or that holds a `.git` entry or whose
parent directory does (a nested repository or a gitfile at a checkout's
`manifests` or `manifests/releases`) raises `ValueError`. One for which git
names a toplevel that does not hold it as its `manifests/releases`, or in which
git cannot run, while a `.git` entry sits two levels above it (such as under a
`core.worktree` setting, or with a bare git directory at `manifests`), raises
`FileNotFoundError`. In each case git would read another repository than the
checkout's. These rules also refuse a selectors directory directly in, or two
levels below, a git working tree's root, such as `<checkout>/scratch-releases`;
no command line passes one. `GIT_CEILING_DIRECTORIES` is ignored, as `GIT_DIR`
and `GIT_WORK_TREE` are. The directory the names come from must hold the
predecessor's selector as given, and every `*.json` entry in it must be a file.
Otherwise the call refuses, and a missing directory or one with no selector
raises `FileNotFoundError`. A `tracked` argument replaces the names: a copy
installed outside a checkout must pass it or `releases_dir`, and `tracked=()`
checks the predecessor's name alone. A name already committed in that directory
is accepted only for a cut that reproduces the committed file byte for byte.
Otherwise the composer refuses, because a tracked selector is never rewritten.
Cut a chain one commit at a time. With the default directory, or a
`releases_dir` that is a checkout's, a cut whose predecessor's selector is not
yet committed is refused (`commit the predecessor's selector first`): commit
`cut1`, then cut `cut2` from it. When a cut adds or replaces a primary scope,
the composer also reads the tracked base scopes from the same directory, unless
`tracked_bases` replaces them. The names, the bases and the committed file the
byte rule compares with are all read when the call runs, from the checkout
`releases_dir` names, or from the checkout the module is imported from. A copy
imported from one checkout and used for a cut in another, without
`releases_dir`, reads the wrong selectors and compares with the wrong file;
pass `releases_dir`, or `tracked` (a tracked name with no file to compare with
is then refused).

**Rendering.** `render_selector` returns the selector text a new cut commits.
Keys are sorted at every level, with a two-space indent, JSON escapes for
non-ASCII characters and a final newline. Each scope uses its one encoding:
`"layer": "base"` for a base scope and no `layer` key for a primary scope.
That is the layout of `us-rulespec-2026-11-11-cms-w6-federal-guidance`.
`tests/test_successors.py` rebuilds that selector byte for byte from its
predecessor:

```python
from pathlib import Path

from axiom_corpus.corpus.releases import ReleaseManifest
from axiom_corpus.corpus.successors import compose_successor, render_selector

releases = Path("manifests/releases")
predecessor = ReleaseManifest.load(releases / "us-rulespec-2026-10-27-ks-liheap.json")
successor = compose_successor(
    predecessor,
    name="us-rulespec-2026-11-11-cms-w6-federal-guidance",
    description=DESCRIPTION,  # the committed text; it names the predecessor first
    add=[("us", "guidance", "2026-10-06-w6-federal-cms-guidance")],
)
text = render_selector(successor)  # the committed selector's bytes
```

On main at `7242a0229`, loading and re-rendering reproduces 85 of the 164
tracked selectors byte for byte. The other 79 use other layouts. The builders
under `scripts/repro/` that reproduce historical cuts keep their own code. Use
the composer for new cuts.

**Lineage findings.** The selector lineage check
(`axiom_corpus.corpus.selector_lineage`) runs in the required `test (3.14)`
job through `tests/test_selector_lineage_repository.py`. Three of the findings
[Selector lineage](release-gate-policy.md#selector-lineage) lists compare base
scopes. The first two compare each cut with its predecessor; the third
compares every tracked selector:

| Finding | Rule |
| --- | --- |
| dropped base (`DroppedBase`) | the cut still carries a pair whose base scope its predecessor selects, and does not select that base as the same base scope: it leaves the base out, selects another version as the pair's base, or selects the base's version as a primary scope |
| layer changed (`LayerChanged`) | a scope the predecessor selects as a primary scope is a base scope in the cut |
| layer conflict (`LayerConflict`) | a scope one tracked selector selects as a base scope and another as a primary scope, unless a dropped base or layer changed finding already names it; no record allows it |

A cut that drops a pair whole gets a dropped pair finding and no dropped base
finding. A base scope added to a pair whose predecessor has no base is not a
finding. The usual fix for a dropped base is to carry it unchanged. The fix for
a layer change is to keep the scope primary. A new base for the pair takes a
version the predecessor does not select, and the old base leaves the cut. A
failing check prints each finding with its fix.

**Base replacements.** A cut that serves a pair over a different base is a
reviewed release decision. Record it in the optional `base_replacements`
section of `manifests/selector-lineage-baseline.yaml`, and pin both selectors
under `selector_digests`:

```yaml
base_replacements:
  - selector: <the cut>
    predecessor: <its predecessor>
    pair: us/statute
    replaced: "<the predecessor's base version>"
    replaced_by: us/statute/<the cut's base version>
    listed_on: <the date of the decision>
    reason: <the decision, and why the new base replaces the old one>
```

Every field is required. Entries are sorted by selector, then pair, with one
entry per selector and pair. `replaced_by` must be a scope of the same pair
with a version other than `replaced`. The entry allows the dropped base when
both selectors match their pins, the entry's predecessor is the cut's
predecessor, that predecessor's base for the pair has the `replaced` version,
the cut selects `replaced_by` as a base scope, and the cut no longer selects
the `replaced` version. An entry that no longer holds is a baseline error,
which fails the check. A layer change has no record, in either direction: a
cut that keeps the replaced base as a primary scope fails even with an entry.
A base that leaves a pair the cut carries without a new base has no record
either. The check holds an entry built in code, rather than loaded from the
file, to the same rules: keyed by its own selector and pair, with `replaced_by`
in that pair. The tracked baseline has no `base_replacements` section, and the
loader reads an absent section as empty.

**Dedup.** `scripts/deduplicate_release_selector.py` leaves alone every base
scope the target declares or a tracked selector it reads marks. It never opens
or cuts a base scope the target declares. Before it opens any artifact, it
refuses a target that selects, as a primary scope, a scope a tracked selector
it reads marks as a base. On the command line it reads the tracked selectors of
the checkout `resolver.cli_repo` finds from `--corpus`; called as a function,
those of `releases_dir`, which defaults to the script's own checkout. It also
reads the tracked selectors of the working directory's checkout (on the command
line), of the checkouts that physically hold the two selector files or a target
scope's artifacts, and of each checkout the resolver recognises that holds a
link at `data`, `data/corpus` or below on those paths as dedup spells them.
Before it opens any artifact, it refuses an artifact that resolves to another
scope's path, an added primary's file that shares its inode with another path, a
link at those places that leads into no checkout, a path that leads through a
symlinked file at or below a guarded place, a checkout whose `manifests` or
`manifests/releases` is a symlink or holds a `.git` entry, and an added
primary's file that a base it knows reaches through a link. To share a corpus
kept outside every checkout, make that directory part of an axiom-corpus
checkout. A checkout outside that list, such as one whose own `data/corpus`
links into the corpus dedup uses, is not read; the threat model's stated limits
list such cases. For a citation path both layers of a pair carry, serving picks
the primary row, so a primary row over a base row is layering, not a duplicate.
Primary scopes alone compete for a citation path. The target selector must
carry every canonical scope in the same layer. A canonical base carried as a
primary scope, or a canonical primary carried as a base, is refused as an
omitted canonical scope. The report lists the base scopes the run left
untouched under `untouched_base_scopes`.

**Consolidation, composition and repair.** Four scripts write new scope
versions or rewrite one in place. Each refuses a base scope it knows before it
writes a new version or moves, rewrites or unlinks an artifact:

- `scripts/consolidate_release_scopes.py` refuses a source or target scope that
  a tracked selector it reads marks as a base, and a jurisdiction, document
  class or version a selector could not spell (a lowercase letter or digit
  followed by lowercase letters, digits, `.`, `_` and `-`). Artifact paths
  strip whitespace and slashes and rewrite `:` and `\`, and a case-insensitive
  filesystem folds case, so `v `, `v/` or `V` would otherwise name the files of
  `v`. It refuses before it fetches, reads or writes any scope artifact.
- `scripts/compose_scope_versions.py` refuses a base constituent or target, and
  a misspelled name, in the same way.
- `scripts/build_ca_rulespec_composite_scope.py` refuses a base scope in its
  selector and consolidates through `consolidate_release_scopes.py`. It refuses
  to promote program roots in place in a scope that a tracked selector it reads
  marks as a base, in a name a selector could not spell, or when a file
  promotion rewrites is also the provisions, inventory or coverage of a base it
  knows, through a link.
- `scripts/repair_plan_cascade_self_containment.py` refuses to repair a scope,
  or to write a new scope, that the release selector it repairs or a tracked
  selector it reads marks as a base, and a scope name a selector could not
  spell. It also refuses a repaired scope's new artifact that already exists; a
  link or a shared file in the sources it moves; and a file or sources directory
  it would unlink or move that a base it knows reaches through a link, compared
  by realpath and by file identity in both directions (the base's provisions,
  inventory, coverage, ingest manifest, its sources directory or a link below
  it, leading to such a file, into a moved directory, or to a directory that
  holds one). It refuses a `--report` path that lies at or below a corpus, lock
  or selector place of `--repo`, of the checkout that physically holds the path,
  or of a checkout that holds a link at one of its guarded places on the path as
  spelled, wherever that place leads (a place that does not exist yet and a
  dangling link at a place included); that lies below an entry that is not a
  directory; that names an input; that is a link (a dangling one included), a
  directory, a shared file or anything but a regular file; or that holds a file
  this script did not write (anything but a previous report).
  `--report /dev/null` is refused: the report has no "drop" mode. It checks the
  report path before it reads `--release` or fetches anything, runs the content,
  place and directory checks again just before it writes the report, before it
  makes any directory, and writes the report to a temporary file that replaces
  the path, so it never writes through a link. Its rewrites of `--release`,
  `manifests/**/*.yaml` and `SIGNING-COMMANDS.md` are not guarded. It must read
  the release's scopes to plan the repair, so its scope and artifact refusals
  come after it fetches and reads every scope the release selects, and before
  its first move, rewrite or unlink.

On the command line, consolidation and composition read the
`manifests/releases` of the checkout `resolver.cli_repo` finds from `--base`
(the corpus CLI's rule), and stop when neither `--base` nor the working
directory is in a checkout; repair reads `--repo`'s. Each also reads the
tracked selectors of the working directory's checkout, of the checkouts that
physically hold the artifact paths it reads or writes, and of each checkout the
resolver recognises that holds a link on those paths as it spells them; repair
also those of the checkout that physically holds `--release`, and the bases
`--release` marks. A checkout outside that list is not read (see the threat
model). Called as functions, the first two take `releases_dir`, which defaults
to the script's own checkout. All three read the tracked base scopes with
`tracked_base_scopes`, which loads every `*.json` selector committed at HEAD in
that checkout (or, for any other directory, on disk) and stops on one that does
not load, on an entry that is not a file, on a selectors directory that is a
symlink, sits in one, is spelled with `..`, or holds a `.git` entry or sits in a
directory that does, on one at which git names another toplevel, or cannot run,
while a `.git` entry sits two levels above it, and on a directory with no
selector. Corpus locks carry no layer, so the tracked selectors are the record
of which scopes are bases. Known limit: a base becomes known to these scripts
once a tracked selector of a checkout they read marks it. Until then they treat
it as any other scope. Commit the selector of a cut that adds a base before
running any of them on that scope. A selector that is only on disk or only
staged does not count; a selector main committed after your branch point counts
only once you merge or rebase main; and a checkout these scripts do not read,
for example a worktree whose `data/corpus` links into the corpus they use,
counts only when you run them from it or through its link.

**Signing.** `scripts/sign_release_scopes.sh` signs the draft's primary scopes
that the predecessor lacks. It skips a base scope the predecessor also has as a
base. The predecessor argument must be the committed file of the selector the
draft names first in its description, the selector the lineage check takes. The
script exits 1 when the draft names no tracked selector, when the file differs
from that selector as committed at HEAD, or, when HEAD has a merge base with
`origin/main` or `main` (as of the last fetch), when that selector is at none
of those merge bases with the same bytes. With no such merge base, only the
HEAD rule applies, so a predecessor first committed on the release branch
passes. It exits 1, before it stages, commits or signs anything, when:

- a selector file cannot be read as JSON, or the draft is not a JSON object with
  a string name (the run reads the draft's name before it stages or signs
  anything);
- the checkout's `manifests` or `manifests/releases` is a symlink or holds a
  `.git` entry (a nested repository or a gitfile): through it git would read
  another repository;
- a selector is not a JSON object, has no list of scopes, or gives a scope that
  is not an object;
- either selector spells a part of a scope in a way a selector cannot, or lists
  a scope twice (this check and the one above run first, and the run reports
  only their lines);
- the draft has a base scope that the predecessor lacks;
- the draft has a base scope that the predecessor has as a primary scope;
- the draft has a primary scope that the predecessor has as a base;
- either selector gives a scope a `layer` other than `"base"`;
- the draft has a primary scope that a selector committed at HEAD under
  `manifests/releases` marks as a base;
- either selector does not load with the selector parser
  (`ReleaseManifest.load`), after the layer checks.

It names every such scope on stderr, one line each. The script reads the
selectors in the project environment (`uv run python`). It reads a draft's
description as the selector parser does: a value that is not a string is turned
into one, as the CI lineage guard reads it. It moves to the toplevel that
`git rev-parse --show-toplevel` names, with exported `GIT_DIR` and
`GIT_WORK_TREE` followed, and its own git commands follow them too, while its
selector reads ignore them. So it reads the HEAD of the checkout it signs only
when both variables, if exported, name one checkout's `.git` and working tree
(the threat model's Terms and limit 11). A base the draft leaves out does not
stop the script. The lineage check reports it as a dropped base, or as a dropped
pair when the cut drops the pair whole. For a base the predecessor does not
carry, the message says that "a base scope enters through its restore manifest".
The restore procedure is not documented yet. It lands with the restoration work
in [#728](https://github.com/TheAxiomFoundation/axiom-corpus/issues/728), which
the message cites. `compose_successor`'s `add_base` puts a new base into a
selector, but a draft that adds a base cannot go through this script.

#### Threat model

The offline checks in dedup, consolidation, composition, repair, the CA
builder, the composer and the signer guard against mistakes, not against
someone who means to get around them. They are not a defence against rewritten
git history, edits made to the checkout while a tool runs, or a deliberate
bypass. A tool refuses to change a scope, or to select it as a primary scope,
when a selector it reads marks that scope as a base, at the artifact paths it
checks. The paragraphs below define which checkouts, selectors and paths those
are.

**Terms.**

- A *checkout* is a git working tree whose HEAD commits at least one
  `manifests/releases/*.json`. The checkout that physically holds a path, and
  the working directory's checkout, are found with
  `git rev-parse --show-toplevel`, with `GIT_DIR`, `GIT_WORK_TREE`,
  `GIT_COMMON_DIR`, `GIT_INDEX_FILE` and `GIT_CEILING_DIRECTORIES` ignored;
  markers on disk play no part. The signer is the exception: it moves to the
  toplevel that `git rev-parse --show-toplevel` prints with the inherited
  variables, and its own git commands follow them, while its selector reads
  ignore them. So with `GIT_DIR` and `GIT_WORK_TREE` exported to one checkout's
  `.git` and working tree, it signs that checkout, by its HEAD; exported
  otherwise, see limit 11.
- A *tracked selector* of a checkout is a `*.json` file committed at HEAD under
  its `manifests/releases`. A selectors directory that is not a checkout's
  `manifests/releases` (a `releases_dir` elsewhere, inside a checkout or not) is
  read from disk as given, byte for byte, unless it is refused as follows. A
  selectors directory is refused when it or its parent directory is a symlink
  (such as a checkout's `manifests` linked to another checkout's) or holds a
  `.git` entry (a nested repository or a gitfile), when it is spelled with `..`,
  and when git names a toplevel that does not hold it as its
  `manifests/releases`, or cannot run there, while a `.git` entry sits two
  levels above it, whatever the directory's names (such as under a
  `core.worktree` setting, with a bare git directory at `manifests`, or with a
  `.git/config` git cannot parse). Through any of these, git or the disk would
  answer for another repository than the checkout's. The rule also refuses
  layouts that would be read correctly: a dangling `manifests` link, a
  `manifests` link into the checkout's own subdirectory, an outside alias
  spelled through a link, a selectors directory directly under a top-level link
  such as macOS's `/tmp`, and one directly in, or two levels below, a git
  working tree's root that is not its `manifests/releases`. No command line
  passes such a directory: each passes `<checkout>/manifests/releases`.
- A checkout's *guarded places* are `data`, `data/corpus`,
  `data/corpus/<artifact class>` and every path below them.
- *Main*, for the signer and for the layer-conflict remedy, means the merge
  bases of HEAD with `origin/main` and with `main`, as of the last fetch.

**Which checkouts a tool reads.** A tool reads the tracked selectors of these
checkouts and of no other:

1. The command-line checkout: the one `resolver.cli_repo` finds from `--corpus`
   (dedup) or `--base` (composition, consolidation and the CA builder), by the
   resolver's rules. Through a link the resolver recognises, that is the
   checkout holding the link; otherwise it is the checkout the path resolves
   into, or the repository that an exported `GIT_WORK_TREE` or a `core.worktree`
   setting names (limit 11). Repair reads `--repo`. A function caller names the
   checkout with `releases_dir`; without it, each script reads its own checkout,
   and the composer the checkout the module is imported from (limit 12). The
   composer reads only this checkout (or takes `tracked` instead), and the
   signer only the checkout it runs in.
2. On the command line of dedup, consolidation, composition, repair and the CA
   builder, the working directory's checkout.
3. The checkout that physically holds each of the run's scope artifact paths
   (below), each of dedup's two selector files, and repair's `--release`.
4. Each checkout that holds a link on one of those paths, or on the working
   directory, as the tool spells it: a directory symlink at one of its guarded
   places that the spelled path passes through. Such a checkout is found by the
   resolver's rules, which recognise a checkout by `src/axiom_corpus` or
   `.axiom/corpus-locks` on disk and follow any inherited `GIT_*` variables
   (limit 11). A path on which a symlinked file stands at such a guarded place,
   or comes after a link at one, is refused rather than followed (see "Which
   artifact paths a tool checks", item 1).

**Which selectors count.** The tracked selectors of those checkouts, and the
selectors the run itself is given: dedup's canonical and target selectors,
repair's `--release`, the CA builder's selector, and the signer's draft and
predecessor. A base is known to a tool once one of these marks it.

**Which artifact paths a tool checks.**

1. The run's own scope artifact paths, spelled through the corpus the tool uses:
   for dedup, the provisions, inventory and coverage of every target scope; for
   composition and consolidation, the inventory, provisions and sources of each
   source version and of the target, and the target's coverage; for repair, the
   coverage, inventory, provisions, sources and ingest manifest of each scope it
   repairs and of each new scope; for CA promotion, its inventory, provisions
   and coverage. Each must resolve to a path that ends in its own artifact kind,
   jurisdiction, document class and version. A link at a guarded place on it
   must lead into a checkout; to share a corpus kept elsewhere, make that
   directory part of an axiom-corpus checkout. Each file dedup or CA promotion
   rewrites in place, and each file in the sources repair moves (repair rewrites
   each as it moves it), must have one link. Only these rewritten files are
   checked for hard links; a tool's source paths are not (limit 8). Repair also
   refuses a new scope's path that already exists and a symlink in the sources
   it moves. A path that leads through a symlinked file standing at a guarded
   place of a checkout the resolver recognises, or reached through a link at
   one, is refused: placed corpus files are regular files, never symlinks
   (`docs/corpus-storage.md`). The same holds for the other paths whose
   checkouts a tool looks up: dedup's selector files and repair's `--release`
   and `--report`.
2. For dedup, repair and CA promotion, the artifact paths of every base the tool
   knows, in the corpus it uses: the base's provisions, inventory and coverage,
   and for repair also its ingest manifest, its sources directory and every
   symlink below it. None may lead, through a symlink, a directory alias or a
   hard link, to a file the tool rewrites or unlinks, or to or into a directory
   it moves. For repair, a base's sources directory and each symlink below it
   also may not lead to a directory that holds such a file or directory. Paths
   are compared by realpath and by the file identity of each existing entry and
   its ancestors, so a case alias or a firmlink spelling counts too. A symlink
   below a base's sources that cannot be followed, because it loops or passes
   through a file, is refused.
3. Repair's `--report` path. Before the fetch it must not lie at or below a
   corpus, lock or selector place (`data`, `data/corpus`, each artifact class,
   `.axiom`, `.axiom/ingest-manifests`, `.axiom/corpus-locks`, `manifests` and
   `manifests/releases`) of `--repo`, of the checkout that physically holds it,
   or of a checkout that holds a link at one of its guarded places on it as
   spelled; limit 14 names the links this rule does not follow. Each place is
   followed to where it leads, a dangling link and a place that does not exist
   yet included: the deepest existing entry on that path is compared with the
   entries on the report's realpath by file identity, and the names below it by
   name, letter case ignored. The nearest existing entry above the report path
   must be a directory. The path must not be the `--release` or `--conflicts`
   file, and it must be absent, or a regular file with one link that holds a
   previous report of this script. Just before the write the content, place and
   directory rules run again, in that order, with the roots found afresh and
   before any directory is made, and the report replaces the path without
   following a link. `/dev/null` is not a regular file, so it is refused: the
   report has no "drop" mode.
4. The signer's predecessor argument: byte for byte the committed selector the
   draft names first in its description, and, when HEAD has a merge base with
   main, at one of those merge bases with the same bytes.
5. A composer cut under a tracked selector's name: byte for byte that committed
   file.

##### Not checked (stated limits)

Each limit lies outside one part of the definition above, named in brackets.

1. [Compared] Whether a scope's bytes match its corpus lock or its signed
   ingest manifest.
2. [Checkouts] A checkout outside the four the definition names, such as a
   corpus copied to a plain directory with no link.
3. [Selectors] A base that no selector the tool reads marks yet.
4. [Selectors] A base that main committed after the checkout's branch point.
   Each tool reads the HEAD of the checkouts it finds; merge or rebase main
   first.
5. [Selectors] A selector that is staged but not committed. Commit it first.
6. [Selectors] A commit on the branch that deletes a tracked selector marking a
   base. From that commit on, the base no longer counts.
7. [Compared] That a tracked selector was never edited after its cut. Only the
   composer refuses a rewrite under the cut's own name, and only the signer
   compares its predecessor with main; the CI lineage guard sees an edit of a
   pinned selector only.
8. [Paths] Hard links on paths a tool does not rewrite. Only the files a tool
   rewrites are checked for hard links (item 1); its source paths are not: the
   sources of composition and consolidation, the files repair reads and then
   unlinks, and dedup's canonical files and base paths.
9. [Paths] Rewrites outside the scope artifacts: the signer's writes, and
   repair's rewrites of its `--release` selector, `manifests/**/*.yaml` and
   `SIGNING-COMMANDS.md`, which follow links and write into shared files.
10. [Tools] Other scripts that rewrite a scope in place:
    `scripts/self_contain_usc_scope.py`,
    `scripts/slim_us_recovery_statutes.py`,
    `scripts/repair_us_release_source_references.py`,
    `scripts/recover_ingest.py`, `scripts/recover_ingest_batch.py` and the
    extract writer in `src/axiom_corpus/corpus/usc.py`. They have no layer
    check (#1002).
11. [Checkouts] A checkout that holds a link but that the resolver does not
    recognise: a sparse checkout without `src/axiom_corpus` and
    `.axiom/corpus-locks`, or any checkout while `GIT_DIR` and `GIT_WORK_TREE`
    are exported to another repository. Such a link, a directory link or a
    symlinked file, counts as no link: the refusal of a symlinked file ("Which
    artifact paths a tool checks", item 1) covers only checkouts the resolver
    recognises. So that checkout's selectors are read only when it is also the
    working directory's checkout, or the one that physically holds a path the
    tool reads, its selector files included. On the command line, `cli_repo`
    then returns the checkout the link leads into, or the repository
    `GIT_WORK_TREE` names, not the checkout given. Git discovery is likewise
    taken as git answers. Under a `core.worktree` setting that names another
    directory, the physical holder of a path, `cli_repo` and the signer take the
    directory git names. When that directory commits no selector, such as a
    plain directory, the physical holder is none, `cli_repo` finds no checkout
    unless markers are on disk there, and the signer reads that directory's
    selectors from disk. Only a reader given the redirected checkout's own
    `manifests/releases` refuses the setting. With `GIT_DIR` and `GIT_WORK_TREE`
    exported to a git directory and a work tree that are not one checkout's, the
    signer runs its git commands on that git directory but reads the tracked
    selectors of the work tree's own repository, or the work tree's disk when it
    holds no `.git` entry. A nested repository at a checkout's guarded place
    (such as `git init` at `data/corpus`) is the physical holder of the paths
    below it, or none when it commits no selector, so the guard does not count
    the checkout around it, though `cli_repo` still finds that checkout by its
    markers. A checkout in which git cannot run, such as one whose `.git/config`
    does not parse, is no physical holder, and `cli_repo` does not find it. A
    mount point or other filesystem redirect at `manifests` is read as git
    answers there.
12. [Checkouts] Called as functions, the scope tools default `releases_dir` to
    the script's own checkout, and `compose_successor`, its byte rule included,
    reads the checkout the module is imported from. A caller that works on
    another checkout passes `releases_dir` (or, for the composer, `tracked`).
13. [Compared] Drop and first-cut records in a `LineageBaseline` that code
    builds: one whose selector or predecessor is absent and unpinned is
    skipped. The baseline file's loader requires both pins; in memory, only
    base replacements get the loader's checks.
14. [Paths] A repair `--report` path that does not exist yet and is where a link
    leads that the place rule in item 3 does not follow: a link below one of
    those places (such as one deeper than `data/corpus/<artifact class>`, one
    below `.axiom/ingest-manifests` or `.axiom/corpus-locks`, or a file link in
    `manifests/releases`) of a checkout the rule reads, or any link of a
    checkout it does not read, such as the working directory's checkout or
    another checkout whose own link leads there. A report path spelled through
    another checkout's linked `.axiom`, `.axiom/corpus-locks` or `manifests` is
    such a case: none of those is a guarded place, so the link does not make
    that checkout a root, and only the checkout the link leads into, if any, is
    checked. The report creates a file where that checkout expects an artifact,
    a lock, an ingest manifest or a selector it does not have yet; an existing
    file is protected by the content rule.
15. [Checkouts, paths] A link held elsewhere that leads into the paths a tool
    uses. A tool knows a base only once a selector it reads marks it, and it
    reads the selectors of the checkouts the definition names. A checkout whose
    own `data` or `data/corpus` link leads into the corpus a tool uses is not
    one of them unless it is the working directory's checkout or holds a
    selector file the tool reads: for example, a worktree whose `data/corpus`
    links to the main checkout's while the tool runs on the main checkout. A
    tool also compares base artifact paths only in the corpus it uses, so a file
    elsewhere that links to a file the tool rewrites is not seen. Likewise, a
    selector file a tool reads (dedup's two selector files, repair's
    `--release`) spelled through a checkout's linked `manifests` is held by the
    checkout the link leads into, so only that checkout's selectors are read on
    its account, not those of the checkout that holds the link. Run the tool
    from the checkout that commits the base, or through its link; commit and
    merge a base's selector before others run tools over that corpus.
16. [Selectors, other readers] Three other readers of tracked selectors read
    the working tree, not HEAD: `selector_lineage.load_tracked_selectors` (the
    CI lineage guard's reader), `release_policy.selectors_selecting`, and
    `scripts/check_release_gate.py`'s `_provenance_check`. The CI guard runs in
    a full checkout, where the working tree and HEAD agree; in a sparse or
    edited checkout these readers miss a hidden selector and count an untracked
    one.
17. [Main] Main as the signer and the layer-conflict remedy see it: the merge
    bases of HEAD with `origin/main` and with `main`, as of the last fetch. A
    selector main gained after the last fetch is at neither; fetch and merge
    main first. When neither ref has a merge base with HEAD, the signer checks
    only that its predecessor is committed at HEAD and named first, so a
    predecessor first committed on the release branch passes; the remedy then
    names no selector.
18. [Paths] A base artifact that leads, through a link, to a path where a tool
    creates a new file: the targets of composition and consolidation, and the
    new scope versions repair writes. Such a link dangles until the tool
    creates the file, and these tools compare no base path with what they
    create.

Later checks enforce what these cannot:

- The CI lineage guard (`tests/test_selector_lineage_repository.py`, part of
  the required `test (3.14)` check) reads every selector of the pull request's
  full checkout. It fails on a dropped base, a layer change or a layer conflict
  that no baseline record allows, and on a pinned selector whose digest changed
  (the digest leaves out the description,
  `src/axiom_corpus/release/manifest.py:187-196`). It does not see a rewrite of
  an unpinned selector, nor a description-only edit of a pinned one.
- The activation gate (`scripts/check_release_gate.py`, once #1001 lands)
  compares an incoming release with the active one before activation: cut-plan
  provenance, base carry-forward and base-only pairs.
- Publication refuses a released triple whose artifacts differ from the
  published ones (`scripts/publish_corpus.py:689-696`), so a local rewrite of a
  released base cannot be published.
- In lock mode, `guard-ingested` rejects tracked corpus artifacts in a pull
  request (`src/axiom_corpus/corpus/ingest_manifests.py:424-429`).

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
