# Agent Ingestion Runbook

This runbook is for Codex agents implementing corpus ingestion work in parallel.
The goal is to make each agent task narrow, reviewable, and safe to merge.

## Operating Model

Each agent owns one jurisdiction and document class on one branch. For the
state statute push, that means one `us-xx/statute` scope from
`manifests/state-statute-agent-queue.yaml`. Agents should avoid shared files
except the adapter registry, CLI wiring, tests, docs, and manifest entries
needed for their own jurisdiction.

The corpus pipeline is source-first. The adapter snapshots official source
material, builds a source inventory, emits normalized provision JSONL, and
writes a coverage report. Supabase loading and R2 publication are separate
controller steps after review.

## Scope Selection

Start with `agent_ready` queue items and official/open candidates from the
source-discovery report. Do not assign `source_access_blocked`,
`blocked_primary_source`, or `vendor_permission_needed` items to extraction
agents; those need an official bulk/source export, a permission or license
path, or cleared official-site access before engineering work is useful. Avoid
`blocked_release_repair` items unless the controller explicitly assigns them;
many of those states already have R2 artifacts but are missing local artifacts
in this checkout, so adapter work is not always the right fix. Do not touch
`done` states except for targeted bug fixes.

For each assigned state, first find the current primary official source. If the
state provides bulk XML, JSON, ZIP, SQL, or downloadable HTML, prefer that over
scraping page-by-page. If no bulk source exists, snapshot the official HTML
index and all official section/chapter pages needed to prove completeness.

Agents may use external citation lists, including PolicyEngine references, only
as offline discovery checklists. Do not import PolicyEngine packages, read
PolicyEngine YAML during production ingestion, or treat a model citation as a
corpus source. Every selected document must be re-fetched from the official
publisher and stored as an Axiom source artifact.

## Adapter Requirements

Adapters should live in the corpus package and return `StateStatuteExtractReport`
or the closest existing report type. They must write:

```text
data/corpus/sources/<jurisdiction>/statute/<version>/...
data/corpus/inventory/<jurisdiction>/statute/<version>.json
data/corpus/provisions/<jurisdiction>/statute/<version>.jsonl
data/corpus/coverage/<jurisdiction>/statute/<version>.json
```

The inventory should represent the official source's own hierarchy. The
provision JSONL should include containers when useful for hierarchy and all
section-level text the official source exposes. `citation_path` values should be
stable, lowercase jurisdiction-prefixed paths such as
`us-wa/statute/42/56/010`.

Every inventory item must name a non-symlink regular source file under the
exact `sources/<jurisdiction>/<document_class>/<version>/...` boundary and
record that file's matching SHA-256. Every provision must cite a source path
from that same inventory. Missing, cross-scope, absolute, or symlinked source
references fail the publication gate.

Do not persist AKN XML. Do not add a second schema for one state. If a source
requires a parser helper, keep it local and covered by tests.

## Smoke Run

Run a small bounded extraction before a full run:

```bash
uv run --extra dev axiom-corpus-ingest <extract-command> \
  --base /tmp/axiom-<jurisdiction>-smoke-corpus \
  --download-dir /tmp/axiom-<jurisdiction>-smoke-download \
  --version <yyyy-mm-dd> \
  --source-as-of <yyyy-mm-dd> \
  --expression-date <yyyy-mm-dd> \
  --limit 10
```

The smoke run should prove that official source discovery, source snapshots,
provision parsing, and coverage comparison all work.

## Full Run

For a full run, write to `data/corpus` and a jurisdiction-scoped download cache:

```bash
uv run --extra dev axiom-corpus-ingest <extract-command> \
  --base data/corpus \
  --download-dir data/statutes/<jurisdiction>/<yyyy-mm-dd> \
  --version <yyyy-mm-dd> \
  --source-as-of <yyyy-mm-dd> \
  --expression-date <yyyy-mm-dd> \
  --workers 4
```

Then recompute coverage explicitly:

```bash
uv run --extra dev axiom-corpus-ingest coverage \
  --base data/corpus \
  --source-inventory data/corpus/inventory/<jurisdiction>/statute/<yyyy-mm-dd>.json \
  --provisions data/corpus/provisions/<jurisdiction>/statute/<yyyy-mm-dd>.jsonl \
  --jurisdiction <jurisdiction> \
  --document-class statute \
  --version <yyyy-mm-dd> \
  --write
```

Coverage must have `complete: true`, no duplicate citation paths, no missing
inventory entries, and no unexpected extras before the branch is ready for
publication review.

## Review Package

Every agent handoff should include the source URL, extraction command, counts,
coverage summary, generated artifact paths, source-reference/hash validation,
and test commands. The controller can then include the scope in a new immutable
named selector. Merging data does not publish it, and an existing release name
is never edited or reused.

## Publication Gate

Only publish after code review and green CI. Commit the exact canonical
selector and every selected artifact, leave the checkout clean, then preflight
the selector:

```bash
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/<immutable-name>.json \
  --dry-run
```

The protected publication workflow then executes the only write path:
conditional SHA-256 R2 writes and exact readback, safe reuse checks against
prior signed scope objects, invisible versioned database staging, direct
pre-sign counts and canonical provision/navigation projection digests,
post-readback deep validation, Ed25519 signing, and signed-object readback. It
locally verifies the signature before a separate Supabase Management API
credential invokes transactional activation; the staging service role cannot
activate. An exact retry reuses identical bytes and immutable scopes without
rewriting them. The workflow does not synthesize missing parents or suppress
projection/refresh errors. See `docs/named-release-publication.md`.
