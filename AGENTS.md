# Axiom Corpus Agent Rules

This repository owns source-first legal corpus ingestion. Prefer the corpus
pipeline under `src/axiom_corpus/corpus/` for new work.

## Workflow Scope

- Use this repository's corpus adapters, manifests, CLI commands, release tooling, and Axiom project instructions as the operating procedure for corpus work.
- Do not use PolicyEngine workflow skills or PolicyEngine implementation skills for Axiom corpus, RuleSpec, encoding, or oracle-parity tasks. PolicyEngine may appear as downstream comparison context, but it does not define the ingestion workflow.
- If a reusable workflow is missing, add or propose an Axiom-specific Codex skill or project instruction instead of borrowing a PolicyEngine skill.

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

## State Statute Work

- Pick one jurisdiction at a time from
  `manifests/state-statute-agent-queue.yaml`.
- Add or repair one source-first adapter, then wire it through
  `extract-state-statutes` or a dedicated CLI command.
- A successful state statute task writes all four scoped artifacts:
  `sources/`, `inventory/`, `provisions/`, and `coverage/`.
- Coverage must be complete before a state is proposed for release promotion.
- Do not publish to R2, load Supabase, merge to `main`, or delete old production
  rows unless the user explicitly asks for publication.

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **axiom-corpus** (24319 symbols, 42158 relationships, 548 execution flows).

> Index stale? Run `node .gitnexus/run.cjs analyze --index-only` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? Bootstrap with `npx`, `bunx`, or `pnpm dlx` — e.g. `bunx gitnexus@latest analyze` (npm 11 npx crash; #1939).

## Always Do

- **MUST run impact analysis before editing.** Use `impact({target: "symbolName", direction: "upstream"})` (MCP) or `node .gitnexus/run.cjs impact "symbolName" --direction upstream --repo .` (CLI fallback); report callers, processes, and risk. Never substitute grep for graph analysis.
- **MUST analyze graph changes before committing.** Use `detect_changes({scope: "all"})` (MCP) or `node .gitnexus/run.cjs detect-changes --scope all --repo .` (CLI fallback). `partial: true` or `truncated: true` is not a clean check — a zero means unseen, not unaffected; re-run it. For regression review: `detect_changes({scope: "compare", base_ref: "main"})` or `node .gitnexus/run.cjs detect-changes --scope compare --base-ref "main" --repo .`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- **MUST treat `risk: UNKNOWN` as unresolved, not as low.** An empty caller set is not evidence the symbol is unused — it can also mean the callers are not resolvable by the index (plain-object property access, dynamic dispatch, cross-language calls). `impact` pairs `UNKNOWN` with a `riskNote` saying so. Confirm with a text search before treating the symbol as safe to change or delete; do not proceed on the strength of a zero.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
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

## CLI

| Task | Read this skill file |
| --- | --- |
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
