# Axiom Corpus Agent Rules

This repository owns source-first legal corpus ingestion. Prefer the corpus
pipeline under `src/axiom_corpus/corpus/` for new work.

## Workflow Scope

- Use this repository's corpus adapters, manifests, CLI commands, release tooling, and Axiom project instructions as the operating procedure for corpus work.
- Do not use PolicyEngine workflow skills or PolicyEngine implementation skills for Axiom corpus, RuleSpec, encoding, or oracle-parity tasks. PolicyEngine may appear as downstream comparison context, but it does not define the ingestion workflow.
- If a reusable workflow is missing, add or propose an Axiom-specific Codex skill or project instruction instead of borrowing a PolicyEngine skill.
- Push branches to this repository, never to a fork: a fork-head pull request run does not receive this repository's Actions variable `AXIOM_CORPUS_INGEST_PUBLIC_KEY`, so the authentication-gate tests in `tests/test_state_snap_manual_queue.py` fail by design. See CONTRIBUTING.md.

## Corpus Architecture

- Do not add durable AKN/Akoma Ntoso outputs to this repository, R2, or the
  Supabase schema.
- Durable corpus artifacts are official source snapshots, source inventory,
  normalized provision JSONL, coverage reports, analytics snapshots, and
  release manifests.
- Treat Supabase `corpus.provisions` as the serving database projection, not as
  the canonical source of truth.
- Use primary official government sources. Do not ingest secondary summaries
  such as State Options Reports, Justia, FindLaw, or LegiScan unless explicitly
  directed for a separate non-canonical experiment.

## Corpus Bytes Outside Git

- When `.axiom/corpus-locks/` exists, protected corpus files
  (`data/corpus/{sources,inventory,provisions,coverage}`) are never tracked in
  git; each scope's lock file pins them by sha256. See `docs/corpus-storage.md`.
- Fetch what a task reads: `axiom-corpus-ingest corpus fetch <scope>` (or
  `--path`, `--release`, `--all`). Code-only tasks fetch nothing; the full test
  suite needs `--all`.
- After an ingest, `sign-ingest-manifest ... --lock --push` writes the scope's
  lock and uploads its new objects; commit the lock with the signed manifest.
  Never `git add -f` corpus files.
- An ingest you were asked to do includes `corpus push` of its own new objects
  (Max, 2026-09-30). They are content-addressed and write-once under R2
  `objects/sha256/`: an upload never overwrites an object and publishes
  nothing. CI fails an ingest pull request until R2 holds every object its new
  lock entries name. Every other R2 write, and release publication and
  activation, still need the user's explicit ask.
- A branch opened before the switch (#774) that tracks corpus files: merge
  `main`, run `axiom-corpus-ingest corpus migrate`, commit, then
  `corpus push --changed-since origin/main`.

## State Statute Work

- Pick one jurisdiction at a time from
  `manifests/state-statute-agent-queue.yaml`.
- Add or repair one source-first adapter, then wire it through
  `extract-state-statutes` or a dedicated CLI command.
- A successful state statute task writes all four scoped artifacts:
  `sources/`, `inventory/`, `provisions/`, and `coverage/`.
- Coverage must be complete before a state is proposed for release promotion.
- Do not publish to R2, load Supabase, merge to `main`, or delete old production
  rows unless the user explicitly asks for publication. (An ingest's own
  `corpus push` of content-addressed objects is not publication; see above.)

## Required Checks

Run focused tests for the adapter and CLI you changed. Before handing off, run:

```bash
uv run --extra dev ruff check .
uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports
uv run --extra dev python -m pytest -q
uv run --extra dev towncrier check
```

For a production-ready state statute scope, also run:

```bash
uv run --extra dev axiom-corpus-ingest coverage \
  --base data/corpus \
  --source-inventory data/corpus/inventory/<jurisdiction>/statute/<version>.json \
  --provisions data/corpus/provisions/<jurisdiction>/statute/<version>.jsonl \
  --jurisdiction <jurisdiction> \
  --document-class statute \
  --version <version> \
  --write
```

## GitNexus index

One shared index serves every session. Where this note and the generated block below differ, follow this note.

- **Home.** The index lives on a locked worktree of `origin/main` at `~/TheAxiomFoundation/_worktrees/gitnexus-index/axiom-corpus`. The graph shows `origin/main` as of the last refresh, not your branch.
- **Refresh.** Run `gitnexus-index refresh axiom-corpus`. `gitnexus-index doctor` checks the setup. Don't run `gitnexus analyze` or a floating runner in a working checkout: `.gitnexusrc` names this index, so GitNexus runs the whole pipeline and then refuses to register a second path. From a session checkout the CLI warns that your cwd is a sibling clone and says to re-run `gitnexus analyze`; ignore that warning.
- **Impact and context.** Pass `repo: "axiom-corpus"` to the MCP tools. The CLI form is `gitnexus impact "symbolName" --direction upstream --repo axiom-corpus`.
- **Your branch's changes.** Call `detect_changes({scope: "compare", base_ref: "<output of git merge-base origin/main HEAD>", repo: "axiom-corpus", worktree: "<absolute path to your checkout>"})`. It diffs your checkout, commits and uncommitted edits alike, against the commit where your branch leaves `origin/main`. Use this call for the block's regression review too, never `base_ref: "main"`: local `main` lags weeks behind on this machine, and `origin/main` counts other people's newer commits as yours. Without `worktree`, and from the CLI, the tool diffs the clean index worktree, so its answer says nothing about your work. `scope: "all"` sees uncommitted edits only.

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
