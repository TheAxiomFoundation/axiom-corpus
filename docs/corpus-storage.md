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
- Hidden files under `.axiom/corpus-locks` (`.DS_Store`, editor swap files)
  are never locks and are ignored in every tree; any other file there that is
  not a lock is an error, and so are staged locks with unresolved merge
  conflicts. A worktree whose lock directory is spelled any other way on disk
  (`.AXIOM/Corpus-Locks`) is refused.
- Locked names must be portable (invariant 9): two paths that differ only in
  case or Unicode form, or a path that is also a directory of another, make
  the lock set invalid.

### Local cache

`$AXIOM_CORPUS_CACHE`, default `~/.axiom/corpus-cache`, holds each distinct
file once, read-only. A writer streams bytes into a temporary file inside the
cache, checks sha256 and size, and publishes the object with `link(2)`, which
succeeds only if the object is absent. On a filesystem without hardlinks it
renames with no-replace semantics instead (`renamex_np(RENAME_EXCL)` on macOS,
`renameat2(RENAME_NOREPLACE)` on Linux). Where neither exists (exFAT, some
network filesystems), it takes an exclusive publish lock in the staging
directory (named by a hash of the object's path), checks the object is still
absent, and renames. A lock older than 30 s, or one this process has waited
on for 30 s (a lock dated in the future by a skewed clock included), belongs
to a dead process and is broken. Two processes breaking the same stale lock at
once could both rename, and the second then replaces the first with identical
verified bytes; that is the one exception to write-once below. Every path gives a complete file its
final name in one step, so no reader ever sees partial bytes under an object's
name, and objects are write-once: no writer replaces an object another
process is cloning.

A reader hashes each object the first time a process uses it and deletes one
whose bytes do not match its name; the next fetch replaces it with verified
bytes. An object whose size differs from a lock entry's is deleted only if
its bytes are wrong: a good object stays even when one lock entry is wrong. A writer that
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
refuses any leftover `.corpus-fetch-` file it finds in a scope). Publish locks
live there too. The one file a fetch may leave inside a scope is the hidden
copy it makes beside a target when the staging directory is on another
filesystem (`EXDEV`), if the process is killed between making that copy and
publishing it. The next fetch
deletes temporaries that came into existence more than a day ago, judged by
ctime: a clone keeps the cache object's old mtime.

Placed files are never symlinks and never share an inode with the cache:
release code rejects symlinked artifact paths, and a shared inode would let an
in-place edit corrupt the shared object. (A file placed with `link(2)` briefly
has a second name, its temporary one, which is removed at once.) A missing file is only ever created, never
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
during the same call (`rolled_back`). It removes only a file that is still as
placed (same inode, size and modification time) and still holds the locked
bytes; the content check catches a same-size rewrite within one coarse
timestamp tick. A file that an extractor or another fetch has rewritten
stays, and fetch reports it as modified. An interrupt is handled without asynchronous
exceptions: on the main thread Ctrl-C only stores a flag (no lock, so a burst
of signals cannot deadlock the handler), each worker logs its own outcome and
the file it placed, and on an interrupt (or a progress callback that raises)
fetch cancels queued work, lets in-flight files finish, and rolls back every
`sources/` directory it left incomplete before raising `KeyboardInterrupt`. A
second Ctrl-C during that cleanup (`uv run` forwards every Ctrl-C twice)
changes nothing, and a Ctrl-C that lands after the last file is still raised
once cleanup is done. A rewrite in the instant between
that check and the removal is the one case not covered. A caller whose fetch succeeded checks afterward that its files
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
  such as `coverage`. Signing, guarding and `sync-r2` see the worktree exactly
  as it is.
- Commands and scripts that list whole artifact directories (`analytics`,
  `artifact-report`, `snapshot-provision-counts`,
  `scripts/validate_citation_paths.py`) refuse a partly fetched tree and name
  the fetch command. `analytics` requires only the versions its `--version`
  glob and `<version>-*` parts match, limited to its `--jurisdiction` and
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
  tracked in git at `H` in any spelling a case- and normalization-insensitive
  filesystem merges: `DATA/corpus/…`, `data/corpus/Provisions/…` and
  `data/corpuſ/…` (long s) all land on the locked path on APFS, and HFS+
  also ignores format characters such as a zero-width non-joiner. The guard
  drops format characters, applies full Unicode case mapping, case folding
  and NFKC to every tracked path (git pathspecs match case-sensitively), and
  also counts a tracked file or symlink standing in for a protected directory
  (`data/corpus/provisions`). That covers every merged spelling we know of; a
  filesystem with another folding rule could add more. It names
  each such path the diff adds or changes, and reports any already tracked
  at `H` in one message.
- **One lock directory.** A tracked file under another spelling of
  `.axiom/corpus-locks` (`.AXIOM/corpus-locks/…`) fails the guard and the
  audit: git and the guard see a different path, but a case-insensitive
  worktree reads it as the lock directory. The worktree loader refuses a lock
  directory spelled any other way on disk. Anything under the lock directory
  that is not a regular file (a submodule, a symlink), and a `.axiom` that is
  not a plain directory, is a lock error at every ref, in the index and in
  the worktree: a submodule's locks would otherwise appear only after
  `git submodule update`, unread by any guard. Hidden names (`.DS_Store`,
  Emacs `.#` lock links) are skipped before that check.
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
audit trusts `main`'s history as it stands: branch protection forbids force
pushes, but it does not bind admins (`enforce_admins` is off), so an admin's
direct push or rebase merge would enter that history unchecked.

Without `--ref`, `--attest` audits `HEAD` and fails if the worktree's lock
files differ from it. CI runs the audit whenever lock files exist. On pull
requests it uses the verifier installed from the base commit, as the guard
does, so a pull request cannot change the verifier's code; the one exception
is the pull request that adds the audit, whose base has none. The workflow
file itself runs as the pull request has it, so a pull request that edits
`.github/workflows/ci.yml` could skip either step: review of workflow changes
(and the admins who can merge past checks) remain the trust root. Push
and scheduled runs audit a branch commit with that commit's own code. The
guard's lock rules run when a change touches lock files or protected paths;
the audit covers every entry on every run. At `dbb69efb` signed ingest
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

Open branches that add corpus files merge `main` after the switch and run
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
  The contract for any tool that writes into a checkout: a protected path
  holds either the bytes its lock pins or fresh extractor output, nothing
  else. A tool that needs other bytes (an older release) uses a worktree at
  that release's commit; writing them over a lock-file checkout would make
  `corpus status` and the resolver treat them as current and let a later
  `sign-ingest-manifest --lock` sign them. Temporary files go under
  `data/corpus/.corpus-fetch-tmp/`, never inside a scope.
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
   sha256, and a missing file is created but never replaced by another
   fetch (save the stale-publish-lock race under Local cache, which replaces
   it with identical bytes). Complete files get their final names in one step (link, no-replace
   rename, or a rename under a publish lock), so no failed or interrupted
   fetch leaves partial bytes under a final name. On filesystems that need the
   publish lock, an extractor that writes the same file without that lock can
   be replaced in the instant between the absence check and the rename. A
   scope's `sources/` directory ends up whole, or the files this call placed
   are rolled back; a file someone else rewrote is kept.
5. **Cache integrity.** Every cache object is written once (save the
   stale-publish-lock race described under Local cache), and a process
   uses it only after checking its size and its hash. A corrupt object is
   deleted and replaced with verified bytes; a good one survives a wrong lock
   entry.
6. **Idempotence.** A second fetch changes nothing.
7. **No links.** Placed files are regular files, never symlinks, and never
   share an inode with the cache.
8. **Guard soundness.** A lock entry change passes only if a signed manifest
   attests it or it equals the base blob at the same path; the full audit
   accepts a `git_blob` only from `main`'s first-parent history.
9. **Portable names.** No two locked paths, and no locked path and a
   directory above another, name one place on a case- and
   normalization-insensitive filesystem, so a lock materializes the same tree
   on APFS, NTFS and Linux. At `dbb69efb` the 55,276 `data/corpus` paths have
   no such collision.

`tests/test_corpus_storage.py` checks as Hypothesis properties the round trip
(1), the partition (2), byte fidelity (4), objects that hash to their names
and are read-only (5), idempotence (6), no links (7) and portable names (9,
with a differential test against a brute-force reference); 3 on real git
trees. `tests/test_corpus_lock_guard.py`
checks 8, including tampered locks. The concurrency and failure clauses of 4
and 5 are pinned by regression tests instead: `tests/test_corpus_storage_review.py`
and `tests/test_corpus_lock_guard_review.py` hold one test per reproduced
review finding, each named after it, including create-only placement, whole
`sources/` directories and write-once publication under concurrency. They cover concurrent writes during
fetch and rollback, concurrent and cross-device publication, interrupted and
failing streams, corrupt and truncated cache objects, partial source
directories, planted and laundered locks, merged spellings of protected paths
and of the lock directory, stale bases, unstaged, malformed and conflicted
locks, and signing after a deletion. Each of the fixes we reverted one at a
time (22 in round 3, 19 in round 4, 10 in round 5, 9 in round 6, 7 in round 7) fails at least one of them. One known gap has no test: the partial-test audit hook's
blind spots, described under Tests and CI.

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
