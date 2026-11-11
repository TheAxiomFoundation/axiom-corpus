# CLAUDE.md

This file gives agent-facing guidance for working in `axiom-corpus`.

## Repository Role

`axiom-corpus` owns official source-document ingestion. It downloads, snapshots,
normalizes, and publishes source text into corpus artifacts and Supabase. It does
not own executable policy encodings.

Encodings live in jurisdiction rules repositories such as `rulespec-us` and
`rulespec-us-co` as RuleSpec `.yaml` files. Encoder and validation behavior lives in
`axiom-encode`.

## Current Architecture

```
official source document
  -> manifest/catalog entry
  -> axiom-corpus-ingest extractor
  -> data/corpus/{sources,inventory,provisions,coverage}
  -> R2 bucket: axiom-corpus
  -> Supabase schema: corpus
  -> corpus.provisions
```

The source document itself may be stored in R2 for provenance. Generated
normalized provision rows are loaded into Supabase. Do not store executable
encodings in this repo.

## Corpus bytes outside git

When `.axiom/corpus-locks/` exists, git keeps one lock file per scope (path,
sha256, size of every file under `data/corpus/{sources,inventory,provisions,coverage}`)
and the bytes live in a shared cache (`~/.axiom/corpus-cache`) backed by R2
`objects/sha256/`. `data/corpus` holds only what has been fetched. See
`docs/corpus-storage.md`.

```bash
uv run axiom-corpus-ingest corpus fetch us-ca/statute       # scopes, --path, --release, --all
uv run axiom-corpus-ingest corpus status                    # present / missing / unlocked
uv run axiom-corpus-ingest sign-ingest-manifest ... --lock  # sign, then lock the scope
```

Code-only work needs no fetch. The test suite reads real corpus data and needs
`corpus fetch --all` (APFS clones: almost no extra disk). CLI commands and
`load_provisions`/`load_source_inventory` fetch the locked inputs they name.

## Infrastructure

- R2 bucket: `axiom-corpus`
- R2 credentials: `~/.config/axiom-foundation/r2-credentials.json`
- Supabase source text: `corpus.provisions`
- Local converter cache root: `~/.axiom/`
- Local encoding scratch root, when needed: `~/.axiom/workspace`

## Commands

```bash
uv sync

# Focused corpus tests
uv run pytest -q -m "not integration and not slow"

# Extract official manifest-driven documents
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version <version> \
  --manifest manifests/<manifest>.yaml

# Extract California CalFresh regulations (CDSS MPP §63 DOCX)
uv run axiom-corpus-ingest extract-california-mpp-calfresh \
  --base data/corpus \
  --version <version> \
  --manifest manifests/us-ca-cdss-mpp-calfresh.yaml \
  --download-dir <local-cache-dir>

# Stage normalized provisions in Supabase. This never changes visibility;
# missing parents fail as corpus defects.
uv run axiom-corpus-ingest load-supabase \
  --provisions data/corpus/provisions/<scope>/<version>.jsonl

# Validate an explicit immutable named selector without external writes.
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/<name>.json \
  --dry-run

# Check that every navigation_nodes scope has matching current_provisions
uv run axiom-corpus-ingest verify-release-coverage

# Content findings of a new scope (page navigation, chrome-prefixed bodies,
# hollow document roots, version pickers); validation fails on unrecorded ones.
# CI checks every locked scope against manifests/release-content-baseline.json.
uv run axiom-corpus-ingest content-check <jurisdiction>/<document_class>/<version>
```

A selector may not select a scope listed in `manifests/withdrawn-scopes.yaml`
unless its entry grandfathers that selector; see `docs/release-gate-policy.md`.

A new selector names the selector it succeeds first in its description, cuts
from the newest selector of its line, and keeps a version of every
`(jurisdiction, document_class)` pair that selector carries, unless
`manifests/selector-lineage-baseline.yaml` records the drop, the fork, or the
selector as the first cut of a line; see
`docs/release-gate-policy.md#selector-lineage`. Its entries are append-only and
dated: a decision about a recorded fork made on a later day is a new entry for
its predecessor, never an edit of an entry from an earlier day.

## Named-release visibility model

`load-supabase` only stages immutable version rows. A tracked named selector is
only a cut plan. `scripts/publish_corpus.py` content-addresses and reads back R2
artifacts, checks exact staged provision and navigation counts, deep-validates, then creates an
Ed25519-signed release object. Publication does NOT move serving.

Activation is a separate, deliberate step (`scripts/activate_release.py`, or
`publish_corpus.py --activate`): `corpus.activate_corpus_release` rechecks counts
and repoints serving. Serving follows a per-`(jurisdiction, document_class)`
active map (`corpus.active_scope_pointer`), so activating a release repoints only
the pairs it carries and never un-serves another jurisdiction; overlaps resolve
last-activation-wins per pair and every takeover is recorded in
`corpus.scope_activation_history` (see axiom-corpus#408). `corpus.current_provisions`
and navigation follow that map's exact version membership. Preview a takeover
with `activate_release.py --dry-run`.

The release name `current`, per-scope `publish`/`unpublish`, publish-on-load,
scope auto-registration, and missing-parent synthesis do not exist. See
`docs/named-release-publication.md`.

## Branches, not forks

Push branches to `TheAxiomFoundation/axiom-corpus` itself, never to a fork: a
fork-head pull request run does not receive this repository's Actions variable
`AXIOM_CORPUS_INGEST_PUBLIC_KEY`, so the authentication-gate tests in
`tests/test_state_snap_manual_queue.py` fail by design. See CONTRIBUTING.md.

## Repo Boundaries

- Source text and provenance: this repo.
- RuleSpec encodings: rules repositories.
- Encoder/validator logic: `axiom-encode`.
- App/browser UI: `axiom.org`.

When a provision repeats a value from another source, represent that in the
rules repo with RuleSpec metadata and source verification. The corpus repo should
only make the source text available.

## GitNexus index

One shared index serves every session. Where this note and the generated block below differ, follow this note.

- **Home.** The index lives on a locked worktree of `origin/main` at `~/TheAxiomFoundation/_worktrees/gitnexus-index/axiom-corpus`. The graph shows `origin/main` as of the last refresh, not your branch.
- **Refresh.** Run `gitnexus-index refresh axiom-corpus`. `gitnexus-index doctor` checks the setup. Don't run `gitnexus analyze` or a floating runner in a working checkout: `.gitnexusrc` names this index, so GitNexus runs the whole pipeline and then refuses to register a second path. From a session checkout the CLI warns that your cwd is a sibling clone and says to re-run `gitnexus analyze`; ignore that warning.
- **Impact and context.** Pass `repo: "axiom-corpus"` to the MCP tools. The CLI form is `gitnexus impact "symbolName" --direction upstream --repo axiom-corpus`.
- **Your branch's changes.** Call `detect_changes({scope: "compare", base_ref: "<output of git merge-base origin/main HEAD>", repo: "axiom-corpus", worktree: "<absolute path to your checkout>"})`. It diffs your checkout, commits and uncommitted edits alike, against the commit where your branch leaves `origin/main`. Use this call for the block's regression review too, never `base_ref: "main"`: local `main` lags weeks behind on this machine, and `origin/main` counts other people's newer commits as yours. Without `worktree`, and from the CLI, the tool diffs the clean index worktree, so its answer says nothing about your work. `scope: "all"` sees uncommitted edits only. The call matches your diff's new line numbers against each symbol's lines at the index commit (the `lastCommit` that `list_repos` shows for axiom-corpus). So it can name the wrong symbols, or none at risk "low", in any file that changed between that commit and your merge-base (`git diff --name-only <index commit> <merge-base>` lists them) and in any file where your own edits add or remove lines above a later change. Read its answer as a list of changed files, and run `impact` by name on each symbol you changed.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **axiom-corpus**.

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact before editing.** Use `impact({target: "symbolName", direction: "upstream"})` or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .`; report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- MUST warn on HIGH/CRITICAL `risk` pre-edit; never use `riskSharedAxes` to waive a HIGH/CRITICAL `risk` warning. Compare File/symbol: MCP File omits axes; Graph-RAG expands File.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- **MUST use `query({search_query: "concept"})` for concepts/flows, `context({name: "symbolName"})` for a named symbol, or `impact` for blast radius, on read-only callers, dependencies, imports, or execution flow.** Graph first; text search only for empty/`UNKNOWN`/literals.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method before MCP/CLI impact analysis.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis, and never read `UNKNOWN` as an all-clear — it means the walk could not answer, which is the one verdict that requires confirming by other means.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit before MCP/CLI graph change analysis.

## Resources

| Resource | Use for |
| --- | --- |
| `gitnexus://repo/axiom-corpus/context` | Codebase overview, check index freshness |
| `gitnexus://repo/axiom-corpus/clusters` | All functional areas |
| `gitnexus://repo/axiom-corpus/processes` | All execution flows |
| `gitnexus://repo/axiom-corpus/process/{name}` | Step-by-step execution trace |

<!-- gitnexus:end -->
