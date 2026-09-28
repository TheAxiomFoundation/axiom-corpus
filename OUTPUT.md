# Issue #744 report

Draft PR: https://github.com/TheAxiomFoundation/axiom-corpus/pull/762

Added **130 provisions**: 15 public-law rows and 115 historical USC rows. Prior-year 26 USC 24 is included, using official OLRC release point 118-209 (except 118-159).

Files changed, grouped:

- Extractor/CLI: `src/axiom_corpus/corpus/public_laws.py`, `src/axiom_corpus/corpus/cli.py`.
- Manifest/identity: `manifests/us-ctc-history-public-laws.yaml`, `schema/citation-path.v1.json`.
- Tests/changelog: `tests/test_corpus_public_laws.py`, `tests/test_corpus_ctc_history.py`, `changelog.d/us-ctc-history.added.md`.
- Complete `sources/`, `inventory/`, `provisions/`, `coverage/` artifacts for `us/statute/2026-09-27-ctc-history-public-laws` and `us/statute/2026-09-27-ctc-history-rp-118-209-title-26`.
- Pipeline documentation: `docs/corpus-pipeline.md`.
- Run note and two draft selectors: `docs/ingest-runs/2026-09-27-ctc-history*`; this report.

Canonical citations and expression dates:

- `us/statute/pl/115/97/11022`, `/a`, `/b`, plus law container: **2017-12-22**.
- `us/statute/pl/119/21/70104`, `/a`, `/a/1`–`/a/3`, `/b`–`/f`, plus law container: **2025-07-04**.
- `us/statute/26/24` and descendants: **2024-12-23**, including old `h/2`, `h/5/B`, `h/7`, and 2021 `i`. Version/date distinguish historical text; current text is unchanged.

Validation:

- New focused pytest: **14 passed**; CLI help regression suite: **6 passed**; Ruff passed; mypy passed for **94 source files**.
- Citation scan passed: **586,573 rows / 435,123 unique paths**.
- Coverage complete: **15/15** public-law and **115/115** historical rows, no missing/extra/duplicate citations.
- Each new scope independently passes release validation: **0 errors, 0 warnings**.
- Related CLI/USC/self-containment/new-test run: **122 passed, 2 timed out** (existing whole-title USC parsing, 60-second limit); all 73 CLI tests passed.
- Towncrier passed on the committed diff.
- Requested offline suite interrupted at whole-corpus scanning; seven transient NC/NY fixture failures passed on rerun.
- Whole-suite attempt (60-second test timeout) interrupted: **660 passed, 7 failed, 17 errors, 47 skipped**. Two CLI help-group failures were fixed; all remaining failures/errors were timeouts. Full-suite success is unverified.
- Full 1,043-scope union deep validation interrupted; structural preservation of all 1,042 predecessor scopes verified. Dispatcher must finish validation.
- CI stops at the unsigned artifact guard (nine artifacts); tests did not run. Draft status retained.

Remaining dispatcher/publication work (exact commands and evidence in `docs/ingest-runs/2026-09-27-ctc-history.md`):

1. Artifacts are **unsigned**. On the clean reviewed commit, dispatcher runs `uv run axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus --jurisdiction us --document-class statute --version <scope-version> --command '<recorded extraction command>' --reasoning-log docs/ingest-runs/2026-09-27-ctc-history.md` for both scope versions above, using the authorized signing environment. Commit the resulting `.axiom/ingest-manifests/us/statute/<scope-version>.json`, then run `uv run axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD`.
2. Reconcile the draft public-law union against the actual active union, preserving all served scopes; its production equivalence is unverified. Promote a reviewed selector to `manifests/releases/<immutable-name>.json`, commit it, run `SIGNING-RUNBOOK.md`'s clean-checkout checks, then `uv run python scripts/publish_corpus.py --release manifests/releases/<immutable-name>.json --repo-root . --base data/corpus --dry-run`.
3. Authorized operator runs `gh workflow run publish.yml -R TheAxiomFoundation/axiom-corpus --ref main -f release=<immutable-name>` (or the canonical selector merge trigger). Publication signs, uploads, stages, and registers; **it does not activate**. Retain its run ID, signed object, name, and content SHA.
4. For the reconciled full public-law union only, obtain separate activation authorization. Run `gh workflow run activate-release.yml -R TheAxiomFoundation/axiom-corpus --ref main -f publish_run_id=<id> -f release=<name> -f content_sha=<sha> -f request_activation=false`; review every takeover, then repeat with `request_activation=true` and approve the protected `release-activation` environment.
5. **Never activate the historical-only release:** it would replace the whole `(us, statute)` serving pair. Historical consumption must explicitly select its version; encoder compatibility remains unverified.

No secrets were read and no signing, publication, registration, or activation was performed. TY2018–2024 remain fail closed until the supervised encoder can ground them; annual IRS revenue procedures were outside this work order.
