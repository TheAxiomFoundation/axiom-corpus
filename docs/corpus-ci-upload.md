# Uploading an ingest's corpus objects from CI

An ingest pull request commits signed ingest manifests
(`.axiom/ingest-manifests/...`) and lock files (`.axiom/corpus-locks/...`).
The bytes they pin are git-ignored and stay on the ingester's machine until
`corpus push` uploads them to R2, which needs R2 write credentials on that
machine. Until R2 holds them, the pull request's CI fails with
`cannot obtain ... no source holds`.

The `Upload signed ingest corpus objects` workflow
(`.github/workflows/corpus-object-upload.yml`) does that upload on a GitHub
runner instead. `corpus push` keeps working for anyone who holds the
credentials. See `docs/corpus-storage.md` for the storage model.

**Use this path only for sources that are already public.** The archive is
not private while a run handles it: see "Who can read the archive" below. For
any other source, a credential holder runs `corpus push`.

## Steps

For pull request `<N>`, on its branch, with the ingested files in
`data/corpus`:

1. **Ingester: pack.** No credentials needed.

   ```bash
   uv run axiom-corpus-ingest corpus ci-pack --changed-since origin/main
   ```

   This writes `corpus-objects.tar`: one member per distinct object that the
   branch's new or changed lock entries name, each named by its sha256. Every
   file is hashed against its lock entry first. A branch that predates the
   command merges `main` first, or runs it from a `main` checkout with
   `--repo <ingest checkout>`.

2. **Ingester: attach the archive to a draft release.** This needs the write
   access that pushing the branch already needs.

   ```bash
   gh release create corpus-upload-pr-<N> --draft \
     --title "Corpus objects for #<N>" \
     --notes "Staging archive for the corpus object upload workflow." \
     corpus-objects.tar
   ```

   A draft release creates no git tag and is visible only to people with
   write access. Do not publish it.

3. **Dispatcher: start the workflow on `main`** with the pull request number
   and the head commit that was reviewed.

   ```bash
   gh workflow run corpus-object-upload.yml --ref main \
     -f pr_number=<N> \
     -f head_sha="$(gh pr view <N> --json headRefOid --jq .headRefOid)"
   ```

4. **Ingester: re-run the pull request's CI**, then delete the draft:
   `gh release delete corpus-upload-pr-<N> --yes`.

A run that fails changes nothing that a second run cannot repeat. A second
run with the same inputs writes nothing and passes.

## What the workflow accepts

The workflow has three jobs. All run only for a `workflow_dispatch` on
`refs/heads/main`, so the workflow file and all code are `main`'s.

`stage` first requires pull request `<N>` to be open, to have its head and
base in this repository, and to be at the `head_sha` the dispatcher gave. A
fork-head pull request already fails this repository's CI by design, and a
closed or merged one has nothing left to unblock, so neither is served. It
then lists the repository's releases, requires exactly one tagged
`corpus-upload-pr-<N>`, requires it to be a draft holding exactly one asset
named `corpus-objects.tar` within the size limit, downloads that asset by id
and passes it on as a run artifact. It does not open the archive. It holds a
`contents: write` token, because GitHub lists draft releases only for tokens
with push access, a `pull-requests: read` token, and no R2 credentials.

`upload` holds the R2 write credentials in its last step only, and a
`contents: read` token. It checks out `main`, fetches the pull request's head
commit as git objects (the pull request's tree never enters the worktree, and
none of its code runs), and requires that commit to be the `head_sha` the
dispatcher gave. `corpus ci-upload` then refuses unless all of this holds:

| Check | Where |
| --- | --- |
| Lock files at the head and at the merge base parse, are canonical, and list only paths of their own scope | `load_locks_at_ref` |
| The plan is the lock entries that are new, or whose bytes changed, since the merge base with `main` | `build_upload_plan` |
| Each changed scope has a manifest at its default path, naming that scope | `_require_signed_scope` |
| The manifest's Ed25519 signature verifies against `AXIOM_CORPUS_INGEST_PUBLIC_KEY`, with the provenance checks `guard-ingested` applies | `verify_ingest_manifest` |
| The scope's lock equals the manifest's applied files: same paths, same sha256 | `_require_signed_scope` |
| At most 5,000 objects and 1.5 GiB per run; the archive is a regular file within the matching limit | `build_upload_plan`, `stage_archive` |
| Every path under `.axiom/corpus-locks` at the head is a canonical lock path; any other name refuses the run without being printed | `_require_strict_lock_tree` |
| The fetched pull request ref is at `head_sha` | `require_ref_at` |
| Every archive member is a plain regular file, named exactly by the sha256 of a planned object, present once, with the lock's size and bytes that hash to that sha256 | `stage_archive` |
| Every planned object that the archive lacks is already in R2 with exactly the pinned bytes; checked before any write | `execute_upload` |

The archive is an uncompressed POSIX ustar file. `stage_archive` parses it
block by block itself and accepts only what `ci-pack` writes: a ustar header
with a correct checksum, for a regular file, with the whole name in the name
field and a plain octal size. Nothing is extracted by name: a member's name
only selects a planned object, and the staged file is named from the plan.
Anything else refuses the whole archive: another name, a path with a
directory, a symlink, a hard link, a directory, a device, a PAX or GNU
extension header (long names, sparse maps, size or path overrides), a
duplicate, a file no changed lock entry names, a truncated file, non-zero
padding, or any non-zero byte after the end-of-archive marker, which is where
a second archive would hide.

Refusal messages quote pull-request data. Every message is reduced to one
line without control or format characters, the job summary HTML-escapes it,
and `ci-upload` turns workflow-command processing off (`::stop-commands::`
with a random token) while it prints its report.

An object's key is `objects/sha256/<xx>/<sha256>`, computed from the lock
entry's sha256 by `content_key`. Writes go through `R2ObjectStore.put`, the
same call `corpus push` uses: a conditional `PutObject` (`IfNoneMatch: *`),
then a readback that must hash to the sha256. An object that already exists
is compared and never replaced; if it holds other bytes the run fails.

The job runs the checks twice: first in a step without R2 credentials, then
again in the step that writes.

`cleanup` runs last, also after a failure. It holds an `actions: write` token
and nothing else, and deletes the run artifact.

## Who can read the archive

- The draft release asset: people with write access to the repository, until
  the ingester deletes the draft.
- The run artifact that carries the archive from `stage` to `upload`: in a
  public repository, **any signed-in GitHub user**, from the end of `stage`
  until `cleanup` deletes it. Its retention is one day, the shortest GitHub
  allows, in case `cleanup` does not run. At that point the archive is not
  yet verified.
- The objects in R2: as for every other corpus object.

The workflow cannot tell whether a source is public. The ingester decides
that before attaching an archive.

## Who can start it

`workflow_dispatch` needs write access to the repository (the `Actions:
write` permission that the Write, Maintain and Admin roles carry). Creating
the draft release needs write access too. The signature is what authorizes
the bytes: a dispatcher cannot make the workflow write an object that no
valid signed manifest names.

## Maintainer setup and known limits

A repository admin creates the `corpus-object-upload` environment before the
first run and restricts it to the `main` branch, as `release-publish` is.
GitHub creates a missing environment on first use with no protection.
Required reviewers are optional: of the existing environments only
`release-activation` has them. With required reviewers, each upload waits for
one approval.

The workflow uses the existing `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` and `R2_BUCKET` secrets and the
`AXIOM_CORPUS_INGEST_PUBLIC_KEY` variable. It needs no new secret.

Known limits, none of which this workflow changes:

- **The `refs/heads/main` conditions are advisory today.** The R2 write
  credentials are repository secrets. The four existing environments hold no
  secrets and the repository has no rulesets, so a workflow file on any
  branch, dispatched by anyone with write access, can name those secrets
  (`mirror-release.yml` records the same note). The conditions protect this
  workflow file, not the credentials. Recommendation for the maintainer: move
  the R2 write secrets into environments restricted to `main`
  (`corpus-object-upload` here, the release environments for the release
  workflows) and delete the repository-level copies. Then only `main`'s
  workflow files can use them.
- **`stage` needs `contents: write`.** GitHub lists draft releases only for
  tokens with push access. That job holds no R2 credentials, never opens the
  archive, and its checkout does not persist the token.
- **Fork, closed and merged pull requests are refused.** The signature check
  does not depend on that, but no case needs them.
- **Actions are pinned by full commit SHA**, with the tag in a comment, as
  `register-release-object.yml` pins them.

## Alternatives considered

- **A no-secret job on the pull request branch builds the archive as a
  workflow artifact.** The bytes exist only on the ingester's machine. A
  runner has nothing to pack, and only a workflow run can create an Actions
  artifact.
- **`pull_request_target`, or `workflow_run` after CI.** Both put
  pull-request-controlled input next to secrets on an automatic trigger. A
  dispatch names one pull request and one reviewed commit.
- **The bytes in a temporary git ref.** That needs no archive and no write
  token, but it puts corpus bytes back into the repository's object store,
  which `docs/corpus-storage.md` moved them out of, and GitHub rejects files
  over 100 MB.
- **A published release or pre-release.** It creates a public git tag for
  every ingest.
