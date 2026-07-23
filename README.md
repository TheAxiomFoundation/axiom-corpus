# Axiom Corpus

**Comprehensive map of government legal sources.**

Axiom Corpus is the unified source of truth for statutes, regulations, guidance, and related source documents that power the Axiom ecosystem.

## Features

- **Federal statutes** — All 54 titles of the US Code from official USLM XML
- **IRS guidance** — Revenue Procedures, Revenue Rulings, Notices (570+ documents)
- **State codes** — NY Open Legislation API, more states coming
- **Regulations** — CFR titles, Treasury regulations, agency rules
- **Provenance** — Every file tracked with fetch date, source URL, checksums
- **REST API** — Query documents by citation, keyword, or path (self-hostable)
- **Change detection** — Know when upstream sources update

## Quick Start

```bash
# Install (uv creates and manages the virtualenv for you)
uv sync

# List the pipeline commands
uv run axiom-corpus --help

# Run the offline test suite
uv run --extra dev pytest -q -m "not integration and not slow"
```

Without [uv](https://docs.astral.sh/uv/), create and activate a virtualenv
first (`python -m venv .venv && source .venv/bin/activate`), then
`pip install -e .` — a bare `pip install -e .` outside a virtualenv does not
put the `axiom-corpus` command on your PATH.

## CLI Usage

The corpus is populated by a manifest-driven ingest pipeline: official
source documents are extracted into `data/corpus/` artifacts, staged into
Supabase, and served only through signed, immutable named releases. The
`axiom-corpus` and `axiom-corpus-ingest` commands are the same CLI under
two names.

```bash
# Extract official manifest-driven documents
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version <version> \
  --manifest manifests/<manifest>.yaml

# Stage normalized provisions in Supabase (staging only — never changes
# what is served)
uv run axiom-corpus-ingest load-supabase \
  --provisions data/corpus/provisions/<scope>/<version>.jsonl

# Validate a named release cut without external writes
uv run --extra dev python scripts/publish_corpus.py \
  --release manifests/releases/<name>.json \
  --dry-run

# Check that every navigation_nodes scope has matching current_provisions
uv run axiom-corpus-ingest verify-release-coverage
```

Step-by-step workflows live in
[`docs/agent-ingestion-runbook.md`](docs/agent-ingestion-runbook.md)
(ingest) and
[`docs/named-release-publication.md`](docs/named-release-publication.md)
(release/publication model); [`CLAUDE.md`](CLAUDE.md) has the condensed
pipeline reference.

> **Deprecated: `axiom crawl`.** The legacy web crawler (`axiom crawl`, backed
> by `src/axiom_corpus/crawl.py`) is superseded by manifest-driven ingest — see
> [CLAUDE.md](CLAUDE.md) and the `axiom-corpus-ingest` commands. It still works
> and emits a `DeprecationWarning`; it is scheduled for removal after 2026-Q3
> unless a consumer objects.

## Python API

```python
from axiom_corpus import AxiomArchive

archive = AxiomArchive()

# Get a specific section
eitc = archive.get("26 USC 32")
print(eitc.title)        # "Earned income"
print(eitc.text)         # Full section text
print(eitc.subsections)  # Hierarchical structure

# Search
results = archive.search("child tax credit", title=26)
for section in results:
    print(f"{section.citation}: {section.title}")

# Get historical version (see status note below)
eitc_2020 = archive.get("26 USC 32", as_of="2020-01-01")
```

> **Status: `as_of` historical versioning is incomplete.** It is honored
> for eCFR regulations (via the eCFR API's native point-in-time support)
> but is currently a no-op on statutes stored in SQLite/Postgres — the
> parameter is accepted and the current version is returned. See
> [`docs/historical-versioning.md`](docs/historical-versioning.md) for
> the known gaps and what full support would require.

## REST API

```bash
# Start the API server
uv run uvicorn axiom_corpus.api.main:app --port 8000

# Get section by citation
curl http://localhost:8000/v1/sections/26/32

# Search
curl "http://localhost:8000/v1/search?q=earned+income&title=26"

# Get specific subsection
curl http://localhost:8000/v1/sections/26/32/a/1

# Historical version
curl "http://localhost:8000/v1/sections/26/32?as_of=2020-01-01"
```

## Data Sources

| Category | Source | Format | Files |
|----------|--------|--------|-------|
| Statutes | uscode.house.gov | USLM XML | 8 titles, 20k+ sections |
| IRS Guidance | irs.gov/pub/irs-drop | PDF/HTML | 570+ documents |
| State Laws | NY Open Legislation | JSON | Tax, Social Services |
| Regulations | eCFR | XML | Treasury, agency rules |

## Architecture

For a visual map of how `axiom-corpus` fits into the wider Axiom Foundation
ecosystem — fetchers, parsers, adapters, storage, the encoder, RuleSpec
repos, axiom-rules-engine, axiom-programs, and the consumer apps — see the
interactive architecture viewer:

- **Live:** <https://axiom-architecture-one.vercel.app>
- **Repo:** <https://github.com/TheAxiomFoundation/axiom-architecture>

It has an External / Internal mode toggle that controls how much detail
shows for each component. Click any node to see what it owns, which
repository it lives in, and how it connects.

### This repo's layout

```
axiom-corpus/
├── src/axiom_corpus/
│   ├── __init__.py
│   ├── archive.py        # Main Axiom archive class
│   ├── models.py         # Pydantic models for statutes
│   ├── models_guidance.py # Models for IRS guidance
│   ├── parsers/
│   │   ├── uslm.py       # USLM XML parser
│   │   └── ny_laws.py    # NY Open Legislation parser
│   ├── fetchers/
│   │   ├── irs_bulk.py   # IRS bulk guidance fetcher
│   │   └── irs_guidance.py
│   ├── api/
│   │   └── main.py       # FastAPI app
│   ├── cli.py            # Command-line interface
│   └── storage/
│       ├── base.py       # Storage interface
│       ├── sqlite.py     # SQLite + FTS5 backend
│       └── postgres.py   # PostgreSQL backend
├── data/                  # Downloaded data (gitignored)
├── catalog/               # Structured document catalog
│   ├── guidance/          # IRS guidance documents
│   ├── statute/           # Statute extracts
│   └── parameters/        # Policy parameters by year
└── sources/               # Raw source archives
```

## Storage

Axiom uses SQLite + FTS5 for local development. For production deployments:

- **Cloudflare R2** — Raw files (PDFs, XML)
- **PostgreSQL** — Parsed content, metadata, full-text search

### Navigation index

The Supabase corpus schema also exposes `corpus.navigation_nodes`, a derived
parent/child serving index for browsing the corpus tree. `load-supabase`
rebuilds the index for the loaded scope by default (pass
`--no-build-navigation` to skip), and `axiom-corpus-ingest
build-navigation-index` (or `scripts/build_navigation_index.py`) can rebuild
it on demand from a provisions JSONL or directly from
`corpus.provisions`. `corpus.provisions` remains the source of truth for
legal text; navigation rows only exist so app navigation can be served from a
simple indexed `parent_path` lookup instead of repeated prefix `LIKE` scans.

```bash
# Rebuild one jurisdiction. --from-supabase prunes stale rows by default,
# since the Supabase snapshot is the full scope.
uv run python scripts/build_navigation_index.py --jurisdiction us-co --from-supabase

# Rebuild one (jurisdiction, doc_type) scope.
uv run python scripts/build_navigation_index.py --jurisdiction us-co --doc-type regulation --from-supabase

# Rebuild from a freshly extracted provisions JSONL. --provisions does NOT
# prune by default, because a local JSONL is often a partial slice of the
# corpus. Pass --replace-scope to prune stale rows in the touched scopes.
uv run python scripts/build_navigation_index.py --provisions data/corpus/provisions/us-co/regulation-2026.jsonl
```

## Deployment

### Local

```bash
# Build and run
uv sync
uv run uvicorn axiom_corpus.api.main:app --port 8000
```

### Docker

```bash
# Build and run
docker build -t axiom-corpus .
docker run -p 8000:8000 -v $(pwd)/axiom.db:/app/axiom.db axiom-corpus
```

## License

Apache 2.0

## Related Repos

- [axiom-rules-engine](https://github.com/TheAxiomFoundation/axiom-rules-engine) — RuleSpec compiler and runtime
- [axiom-encode](https://github.com/TheAxiomFoundation/axiom-encode) — Encoder pipeline for generating RuleSpec from source law
- [axiom-programs](https://github.com/TheAxiomFoundation/axiom-programs) — Oracle-comparison toolkit (Axiom vs PolicyEngine, TAXSIM, ACCESS NYC)
- [axiom-architecture](https://github.com/TheAxiomFoundation/axiom-architecture) — Interactive architecture viewer for the whole ecosystem ([live](https://axiom-architecture-one.vercel.app))
- [axiom-demo-shell](https://github.com/TheAxiomFoundation/axiom-demo-shell) — Landing page embedding the three demos
- [axiom-foundation.org](https://github.com/TheAxiomFoundation/axiom-foundation.org) — Public web app
- [rulespec-us](https://github.com/TheAxiomFoundation/rulespec-us) — US federal rules in RuleSpec
