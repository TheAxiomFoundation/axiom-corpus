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
```

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

## Repo Boundaries

- Source text and provenance: this repo.
- RuleSpec encodings: rules repositories.
- Encoder/validator logic: `axiom-encode`.
- App/browser UI: `axiom-foundation.org`.

When a provision repeats a value from another source, represent that in the
rules repo with RuleSpec metadata and source verification. The corpus repo should
only make the source text available.

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
