# Contributing

Use short-lived branches off `main` and open a pull request back to `main`.
Keep PRs focused, describe the checks you ran, and wait for CI before merging.

## Branches, not forks

Org members have write access to this repository, so push your branch to
`TheAxiomFoundation/axiom-corpus` and open the pull request from it. Do not
work from a fork: a fork-head pull request run does not receive this
repository's Actions variable `AXIOM_CORPUS_INGEST_PUBLIC_KEY`, so the
authentication-gate tests in `tests/test_state_snap_manual_queue.py` (and
`guard-ingested`, when the change touches protected corpus artifacts,
manifest-attested reasoning logs, or the ingest manifests attesting them) fail
by design, and that is what fails the `test` job. The `FAIL Required test
coverage` line in the same log is informational, not the failure (a real
coverage failure prints `ERROR: Coverage failure`). This is the trust boundary
working as intended and does not depend on the author's permissions (#600's
author already had write access). Never weaken those tests or embed key material
to get past it (#357 tried a checked-in fallback key and was closed). If you
already opened a fork PR, push the same commits to a branch here and open a new
PR from it, or ask a maintainer to mirror the fork head into a same-repo branch
(precedent: #600 → #606). Contributors without write access take the maintainer
path.

## Pull request flow

1. Create a branch from an up-to-date `main` in this repository (not a fork).
2. Make the smallest coherent change and include tests for behavior changes.
3. Add a Towncrier fragment under `changelog.d/` unless the PR is docs,
   tests-only, or otherwise has no user-visible release note.
4. Open the PR to `main` and complete the PR template.
5. Merge after review approval and green CI.

Towncrier fragment categories are `breaking`, `added`, `changed`, `fixed`, and
`removed`. Name fragments descriptively, for example
`changelog.d/historical-versioning.fixed.md`.

## Local checks

CI runs the changelog draft, Ruff, mypy, tests with coverage, and a PostgreSQL
smoke check. Run the relevant subset locally before opening the PR:

```bash
uv sync --extra dev
uv pip install pytest-cov pytest-timeout
uv run towncrier build --draft --version 0.0.0
uv run ruff check .
uv run mypy src/axiom_corpus/corpus --ignore-missing-imports
uv run pytest -v --cov=axiom_corpus --cov-report=term-missing --cov-config=pyproject.toml --timeout=60
```

## Repo notes

- Generated `data/` and `sources/` files are local artifacts; do not commit them
  unless the PR explicitly adds a fixture or catalog source.
- Integration tests and live-source fetches should be isolated from the default
  offline test path.
- Keep storage, fetcher, and API changes covered by focused tests because they
  affect downstream encode and app workflows.
