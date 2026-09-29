# Corpus storage outside git

Git records which corpus bytes a commit contains. A shared, content-addressed
store holds the bytes. This document describes that split: the lock files git
keeps, the local cache and R2 store that hold the bytes, the `corpus` commands
that move bytes between them, and the checks that keep signed ingest manifests
and named releases verifiable.

## Why

At `origin/main` `dbb69efb` (2026-09-29) git tracked 60,153 files and
15.04 GB. `data/corpus` accounted for 55,276 files and 14.92 GB of that: PDFs
7.18 GB, JSONL 2.31 GB, JSON 2.24 GB, HTML 1.51 GB, XML 0.76 GB. Every
checkout, worktree and agent job paid for the whole corpus; one machine held
about 85 checked-out copies, roughly 650 GB. A job that only changes code needs
none of it.

## Layout

```text
.axiom/corpus-locks/<jurisdiction>/<document_class>/<version>.json   git: one lock file per scope
data/corpus/{sources,inventory,provisions,coverage}/...             worktree: fetched, git-ignored
~/.axiom/corpus-cache/objects/sha256/<xx>/<sha256>                 local cache, shared by checkouts
r2://axiom-corpus/objects/sha256/<xx>/<sha256>                     remote store
```

The four protected prefixes are the ones the ingest guard already protects.
Everything else under `data/corpus` (`anchors/`, `manifests/`, `migrations/`,
`snapshots/`, 0.7 MB) stays tracked in git.

Code keeps reading `data/corpus/...`. `.gitignore` already ignores `data/`
(every corpus file entered git through `git add -f`), so fetched files never
show up as changes.

### Lock files

One lock file per scope lists every protected file of that scope:

```json
{
  "schema_version": "axiom-corpus/corpus-lock/v1",
  "jurisdiction": "us-ca",
  "document_class": "statute",
  "version": "2026-09-01-rtc",
  "files": [
    {"path": "data/corpus/coverage/us-ca/statute/2026-09-01-rtc.json", "sha256": "…", "size": 812, "git_blob": "…"},
    {"path": "data/corpus/sources/us-ca/statute/2026-09-01-rtc/leginfo/17041.html", "sha256": "…", "size": 20314}
  ]
}
```

- `path` is the repository path that signed ingest manifests and release
  objects already use.
- `sha256` and `size` pin the bytes. `git_blob` appears on entries that moved
  out of git; it names the blob that held the same bytes, so git history can
  still serve them.
- A path belongs to the scope its segments name: `sources/<j>/<dc>/<v>/…`,
  `inventory/<j>/<dc>/<v>.json`, `provisions/<j>/<dc>/<v>.jsonl`,
  `coverage/<j>/<dc>/<v>.json`. At `dbb69efb` all 55,269 protected files map
  to exactly one of 1,903 scopes.
- The encoding is canonical: fixed key order, entries sorted by path, one
  entry per line, ASCII, final newline. Readers reject any other bytes, so two
  writers of one lock produce identical files.
- In a worktree, hidden files under `.axiom/corpus-locks` (`.DS_Store`, editor
  swap files) are ignored; any other file there that is not a lock is an
  error. Staged locks with unresolved merge conflicts are an error too.

### Local cache

`$AXIOM_CORPUS_CACHE`, default `~/.axiom/corpus-cache`, holds each distinct
file once, read-only. A writer streams bytes into a temporary file inside the
cache, checks sha256 and size, and publishes the object with `link(2)`, which
succeeds only if the object is absent. On a filesystem without hardlinks it
renames with no-replace semantics instead (`renamex_np(RENAME_EXCL)` on macOS,
`renameat2(RENAME_NOREPLACE)` on Linux). Only where neither exists does it
create the object exclusively (`O_EXCL`) and copy into it, deleting the object
if the copy fails. Objects are therefore write-once: no writer replaces an
object another process is cloning.

A reader deletes an object whose size is wrong. It also hashes each object the
first time a process uses it, and deletes one whose bytes are wrong. Either
way, the next fetch replaces the object with verified bytes. A writer that
loses the race to publish checks the object that won, and replaces it if it is
corrupt. Placing files from a warm cache into a fresh checkout therefore reads
each object once per process. For a full fetch that is about 15 GB of reads.
Files already in place are skipped without reading the cache.

### Remote store

R2 bucket `axiom-corpus`, key `objects/sha256/<xx>/<sha256>`: the key
`content_addressed_r2_key` already produces and release publication already
writes. Fetch also reads a local git blob named by `git_blob` and, as a last
resort, the legacy path-keyed objects that `sync-r2` wrote. The cache accepts
bytes from any source only after they hash to the lock's sha256.

## Commands

All live under `axiom-corpus-ingest corpus`:

| Command | Effect |
| --- | --- |
| `corpus fetch [SCOPE…] [--all] [--release SELECTOR] [--path PATH] [--paths-from FILE]` | Place locked files in `data/corpus` |
| `corpus status [SCOPE…] [--verify]` | Count present, missing, modified and unlocked files (hidden files included) |
| `corpus lock SCOPE… [--push] [--drop-missing]` | Hash scopes' files into their locks and cache the bytes; refuses hidden files such as `.DS_Store` |
| `corpus push [SCOPE…\|--all\|--changed-since REF] [--dry-run]` | Upload locked objects R2 lacks |
| `corpus verify [--ref REF] [--remote] [--changed-since REF] [--attest]` | Check lock files; with `--remote`, check R2 holds every object; with `--attest`, audit every entry (see Guard) |
| `corpus migrate [--ref REF] [--seed-cache]` | Move tracked protected files into lock files |

A `SCOPE` is `<jurisdiction>[/<document_class>[/<version>]]`.

### Fetch

For each selected lock entry, fetch:

1. skips a destination that already holds the locked size (with `--verify`,
   the locked sha256);
2. takes the object from the cache, or fills the cache from a local git blob,
   R2, or a legacy path key, in that order;
3. places the file as a copy-on-write clone of the cache object:
   `clonefile(2)` on APFS, `FICLONE` on Linux filesystems that support it, a
   plain copy otherwise.

`--no-cache` streams verified bytes straight into place. CI uses it: runners
have no copy-on-write clones, so a cache would double disk use.

Bytes on their way into a checkout wait in `data/corpus/.corpus-fetch-tmp/`,
on the same filesystem but outside every scope, so an interrupted fetch never
leaves a file that `corpus lock` or signing would pick up (`corpus lock`
refuses any leftover `.corpus-fetch-` file it finds in a scope). The next fetch
deletes temporaries more than a day old.

Fetch never creates symlinks or hardlinks in `data/corpus`: release code
rejects symlinked artifact paths, and a hardlink would let an in-place edit
corrupt the shared object. A missing file is only ever created, never
replaced: if an extractor writes it while the bytes are on their way, that
file stays and fetch reports it as modified. Fetch never overwrites a file
whose bytes differ from the lock unless `--force`.

A scope's `sources/` directory is fetched all or nothing. Code enumerates a
scope's sources by listing that directory (release content, signing, the
repair scripts), so half a directory would read as a smaller scope. Selecting
or resolving any source file brings the whole directory, even when that file
is already present, so a directory left partial by a killed process is
completed by the next fetch that touches it. A process checks each scope's
directory once.

When one of a directory's files fails, fetch removes the files it placed there
during the same call (`rolled_back`). It removes only a file that is still
exactly as placed (same inode, size and modification time). A file that an
extractor or another fetch has rewritten since then stays, and fetch reports
it as modified. A caller whose fetch succeeded checks afterward that its files
are still there, because another process's rollback may have removed some. It
fetches missing files again once, and then fails.

### Resolver

Code that reads `data/corpus` paths gets the same guarantee without a
separate command (`axiom_corpus.corpus.resolver`):

- `load_provisions` and `load_source_inventory` fetch a locked file that is
  absent. Before, `load_provisions` returned an empty tuple for a missing
  file, which would have read an unfetched scope as empty. With fetching off
  (`AXIOM_CORPUS_NO_FETCH=1`) a locked, absent file raises instead.
- The CLI fetches the inputs a command names before it runs: paths under the
  protected prefixes and release selectors, plus the
  `--jurisdiction/--document-class/--version` scope for read-only commands
  (`coverage`, `analytics`, `artifact-report`, and others). Signing, guarding
  and `sync-r2` see the worktree exactly as it is.
- Commands and scripts that list whole artifact directories (`analytics`,
  `artifact-report`, `snapshot-provision-counts`,
  `scripts/validate_citation_paths.py`) refuse a partly fetched tree and name
  the fetch command. `analytics` requires only the version it reports (and
  that version's `<version>-*` parts), limited to its `--jurisdiction` and
  `--document-class` filters. `scripts/audit_us_release_publishability.py
  --repair-derived` fetches a scope's locked artifacts before deciding what
  to regenerate, so it never writes a stand-in for an unfetched one. The
  manifest builders' collision checks and
  `scripts/recover_ingest_batch.py` fetch the provisions they list, and the
  scripts that compose, consolidate, re-version or repair scopes fetch their
  input scopes before listing them (a script that rewrites its own scope
  fetches it first, never after its writes).
- `build_release_content` and `scripts/publish_corpus.py` fetch the selected
  scopes before hashing.
- `ensure_corpus_paths`, `ensure_corpus_scopes`, `resolve_corpus_path` and
  `require_materialized` are the building blocks.

With no lock files every one of these does nothing, so the same code runs
before and after the switch. Once one of them consults the locks, lock files
that fail to parse make it raise: an invalid lock must not read as "no
locks". Reading a file that is already present does not consult the locks, so
`load_provisions` on a present file does not notice a broken lock; source
files are the exception, since they check their siblings. `corpus`
commands, the test session and CI read every lock first. Paths resolve
through symlinked spellings, and a command's `--base` may be relative or
absolute and given from any directory.

## Ingest

1. An extractor writes the scope under `data/corpus` (git ignores it).
2. `sign-ingest-manifest --lock --push` signs the manifest from a clean
   tracked tree, as before, then writes the scope's lock, clones the files
   into the cache, and uploads objects R2 lacks.
3. One commit carries the signed manifest and the lock file.

`corpus lock` refuses to drop a locked file that is absent from the worktree,
because an unfetched file and a deleted one look the same on disk. Signing
with `--deleted-file` drops exactly the named files; `corpus lock
--drop-missing` confirms every absence. Either way the signed manifest must
mark each dropped file `deleted`. Signing never fetches, so a file deleted on
purpose stays deleted.

## Guard

`guard-ingested` keeps its checks for tracked files and adds lock rules. For
base `B` and head `H`, lock files and base blobs are compared at the merge
base of `B` and `H`, the same commit the changed-path diff uses; in worktree
mode, lock files not yet staged are checked too:

- **Well-formed locks.** Every lock at `H` parses, is canonical, sits at the
  path its scope names, and lists only protected paths of that scope, each
  once. A lock that fails to parse fails the guard.
- **One representation.** Once `H` has lock files, no protected path may be
  tracked in git at `H` in any letter case: `DATA/corpus/…` or
  `data/corpus/Provisions/…` lands on the locked path on a case-insensitive
  filesystem. Git matches pathspecs case-sensitively, so the guard lists
  every tracked path and folds case itself. It names each such path the diff
  adds or changes, and reports any already tracked at `H` in one message.
- **Moved files.** A protected path tracked at `B` and untracked at `H`
  passes when a lock at `H` carries the base blob's sha256 and size (and, when
  the entry names one, its blob id); otherwise a signed manifest must mark it
  `deleted`.
- **New or changed entries.** Every other lock entry whose sha256 or size
  differs from `B` needs a valid signed ingest manifest (signature, clean-root
  provenance, ancestor commit) whose `applied_files` has the same path and
  sha256. The guard runs the existing content checks on those bytes, read from
  the worktree, cache, git or R2, and fails when it cannot read them.
- **Blob ids.** Whenever an entry's content or `git_blob` changes, the
  `git_blob` must name a local blob holding exactly the locked bytes.
- **Removed entries.** A path dropped from every lock needs a signed manifest
  marking it `deleted`.

CI installs the guard from the pull request's base commit, so the guard that
checks the switch is the one this change adds. The guard only sees changes, so
`corpus verify --attest` checks every lock entry at a commit. Each entry
needs one of these:

- a valid signed manifest attesting its path and sha256;
- a `git_blob` holding its bytes, which some commit on the audited commit's
  first-parent history held at that path.

The repository merges pull requests only with merge commits, so the
first-parent chain is the sequence of states `main` itself held. Bytes that a
pull request committed and removed again before merging never qualify. The
chain is trusted as `main`'s own history, so branch protection is part of this
check: a direct push to `main` would enter that history.

Without `--ref`, `--attest` audits `HEAD` and fails if the worktree's lock
files differ from it. CI runs the audit whenever lock files exist, using the
verifier installed from the base commit, just as it does for the guard. A pull
request therefore cannot loosen its own audit. At `dbb69efb` signed ingest
manifests attest 55,239 of the 55,269 protected files by exact path and
sha256, and none contradicts a tracked file; the other 30 predate the manifest
regime and enter the locks as moved files.

## Releases

`build_release_content` still hashes every selected artifact from
`data/corpus` and records its content-addressed R2 key.
`_require_tracked_release_inputs` accepts an artifact that git tracks or that
a lock committed at `HEAD` pins with the same sha256 and size, and requires a
locked scope's artifacts to equal its lock entries exactly. A release object's
git commit therefore still identifies exact bytes, and a partly fetched scope
cannot be signed.

## Tests and CI

The tests read real corpus data, often every scope of a release selector
(about 11 GB of the 15 GB), so the suite runs on a fully fetched checkout.
Once lock files exist, `tests/conftest.py` stops the session if any locked
file is absent or any lock file is invalid. `AXIOM_CORPUS_PARTIAL_TESTS=1`
runs on a partial tree instead (the PostgreSQL job, which reads no corpus
files, uses it), and an audit hook then fails the session if a test opens a
locked file that is absent. The hook sees only `open` in the test process: a
test that checks `exists()`, lists a directory, or reads in a subprocess is
not caught, which is why real runs use the full tree.

CI jobs fetch before they read, and skip the fetch when no lock files exist:

- `test`: `corpus verify --remote --changed-since <base>` (every entry on
  pushes and the daily run), then `corpus fetch --all --no-cache`. The job's
  full-history checkout serves moved files from git objects.
- `citation-path-grammar`: `corpus fetch --path data/corpus/provisions`.
- `validate-release`: fetches every selector's scopes, then validates with
  `AXIOM_CORPUS_NO_FETCH=1`, under which a missing locked file fails loudly.
- `test` also runs `corpus verify --attest --ref <commit>` over every lock
  entry, right after the guard and with the same base-installed verifier.
- The guard reads new lock entries' bytes for its content checks.

These steps read R2 with `R2_CORPUS_READ_ACCESS_KEY_ID` and
`R2_CORPUS_READ_SECRET_ACCESS_KEY`, a read-only token separate from the
read-write `R2_*` keys publication uses, because the steps run pull-request
code. Fork-head pull requests receive no secrets and fail, as they already
fail the ingest-key checks.

## Migration

Two pull requests:

1. **Tooling** (this change): lock format, cache, fetch, resolver, guard and
   release support, CI steps, documentation. With no lock files every new
   path is inert, so behavior on `main` does not change.
2. **Switch**: `corpus migrate` writes all lock files and removes the
   protected files from the index in one commit. No history rewrite: old
   commits keep their files, so every existing corpus pin keeps working.

Preconditions for the switch:

- R2 holds every locked object (`corpus push --all`, then
  `corpus verify --remote` passes);
- the read-only CI token exists;
- the one-off `scripts/repro/*` reproductions fetch their input scopes
  ([axiom-corpus#770](https://github.com/TheAxiomFoundation/axiom-corpus/pull/770));
- axiom-encode fetches after checking out a corpus ref (below).

Open branches that add corpus files rebase onto the switch and run
`corpus migrate`, which moves their added files into locks.

After the switch a worktree of `main` costs about 130 MB plus what it fetches,
and fetched files share blocks with the one cache.

### Dry run at `dbb69efb`

On a scratch branch:

- `corpus migrate` hashed 55,269 files (14.92 GB) into 1,903 lock files
  (20 MB) in 64 s.
- `guard-ingested` passed the migration commit in 33 s: every moved file
  matched its base blob, with no manifest needed.
- Four tampered variants each failed with the right message: a changed sha256,
  a dropped entry, an unattested new entry, and a file left tracked beside the
  locks.
- Fetched files matched their git blobs byte for byte and were APFS clones.
- With every locked file fetched, the full test suite passed: 4,850 passed and
  105 skipped. The 20 `tests/test_provision_anchors.py` CFR skips also skip on
  `main`, because their provisions file was renamed in July.

### R2 completeness before the switch

A read-only check at `dbb69efb` hashed all 55,276 `data/corpus` files from git
objects, and downloaded and hashed every R2 object it relied on:

| R2 holds the file byte for byte | Files | Bytes |
| --- | ---: | ---: |
| only under `objects/sha256/` | 52,051 | 11.64 GB |
| under `objects/sha256/` and its path key | 1,856 | 0.44 GB |
| only under its path key | 347 | 0.13 GB |
| nowhere | 1,022 | 2.71 GB |

The 1,022 missing files come from 232 scopes (184 ingested in August or
September 2026; 22 named by a tracked selector) plus the 7 non-protected files
that stay in git. Fetch reads `objects/sha256/` first because path keys are
mutable, so a complete remote also needs the 347 path-only files: 1,335
objects, 2.62 GB. On the migrated tree, `corpus verify --remote` reported
exactly those 1,362 files.

## Consumers outside this repository

- `axiom-encode` reads `data/corpus/provisions/...` from an `axiom-corpus`
  checkout at each encoding repo's pinned `axiom-corpus-ref`. Existing pins
  predate the switch and keep their files. Before any encoding repo re-pins
  past the switch, axiom-encode must place a pinned release's files in a
  lock-file checkout
  ([axiom-encode#1742](https://github.com/TheAxiomFoundation/axiom-encode/pull/1742)).
- `axiom.org` counts `data/corpus/provisions/` paths in GitHub trees for a
  status page; since
  [axiom.org#278](https://github.com/TheAxiomFoundation/axiom.org/pull/278) it
  counts lock-file paths as well.

## Invariants

1. **Lock round trip.** `parse(serialize(lock)) == lock`, and
   `serialize(parse(bytes)) == bytes` for every canonical lock.
2. **Scope partition.** Every lock entry lies in its lock's scope; no path
   appears in two locks.
3. **Conservation at the switch.** The lock paths equal the protected paths
   tracked at the base, and each entry's sha256, size and `git_blob` equal
   that blob's.
4. **Fetch fidelity.** After a fetch, every placed file hashes to its lock
   sha256, and a missing file is created but never replaced. Files appear
   under their final names by link or no-replace rename, so a failed file is
   never partly written there. The one exception is the exclusive-copy
   fallback, used only on filesystems with neither hardlinks nor no-replace
   renames: a failed copy is removed, but a process killed mid-copy leaves a
   short file. In the cache that file has the wrong size and is deleted on
   next use; in a checkout, `corpus status` reports it as modified. A scope's
   `sources/` directory ends up whole, or the files this call placed are
   rolled back, and a file someone else rewrote is never removed.
5. **Cache integrity.** Every cache object is written once, and a process
   uses it only after checking its size and its hash. A corrupt object is
   deleted and replaced with verified bytes.
6. **Idempotence.** A second fetch changes nothing.
7. **No links.** Placed files are regular files, never symlinks, and never
   share an inode with the cache.
8. **Guard soundness.** A lock entry change passes only if a signed manifest
   attests it or it equals the base blob at the same path.

`tests/test_corpus_storage.py` checks 1, 2, 4, 5, 6 and 7 as Hypothesis
properties and 3 on real git trees; `tests/test_corpus_lock_guard.py` checks
8, including tampered locks. `tests/test_corpus_storage_review.py` and
`tests/test_corpus_lock_guard_review.py` hold one regression test per
reproduced review finding, each named after it. They cover concurrent writes
during fetch and rollback, interrupted fetches and publication, corrupt and
truncated cache objects, partial source directories, planted and laundered
locks, differently cased paths, stale bases, unstaged, malformed and conflicted
locks, and signing after a deletion. Deliberately breaking each fix fails its
test. One known gap has no test: the partial-test audit hook's blind spots,
described under Tests and CI.

## Alternatives considered

- **Git LFS.** GitHub's LFS storage and bandwidth quotas would bill every CI
  checkout, and LFS writes a full copy into each worktree, so it would not fix
  the disk problem.
- **DVC or git-annex.** Both implement cache-plus-remote with pointer files.
  DVC keys objects by MD5, while signed ingest manifests and release objects
  key by sha256 and R2 already stores release artifacts under sha256 keys;
  either tool would add a second object layout and pointer format for the
  guard to reconcile.
- **Sparse checkout or partial clone alone.** Both keep code-only jobs small
  without new tooling, but every job that needs corpus bytes still writes its
  own full copy, ingest pull requests keep adding blobs to the pack, and
  nothing shares bytes across worktrees.
- **Symlinks or hardlinks into the cache.** Release and validation code
  reject symlinked artifact paths; hardlinks let an in-place write corrupt the
  shared object.
