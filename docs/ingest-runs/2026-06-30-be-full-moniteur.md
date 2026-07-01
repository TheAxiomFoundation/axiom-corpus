# Belgium Full Moniteur Statute/Regulation Discovery

Run date: 2026-06-30

Official upstream:

- Belgian Official Gazette dataset catalog:
  `https://data.gov.be/fr/datasets/fpsjust-moniteur`
- Daily Moniteur summary endpoint:
  `https://www.ejustice.just.fgov.be/cgi/summary.pl`
- Article source endpoint:
  `https://www.ejustice.just.fgov.be/cgi/article.pl`

Scope:

- `Lois, décrets, ordonnances et règlements`
- `Autres arrêtés`

The crawler filters these Moniteur sections to titles that can be classified as
statutes or regulations, then writes a corpus manifest of official `article.pl`
sources. The extractor snapshots those article pages and emits article-level
provisions where the Moniteur HTML exposes article headings.

Smoke command:

```bash
uv run --extra dev axiom-corpus-ingest discover-belgian-moniteur \
  --start-date 2026-06-01 \
  --end-date 2026-06-01 \
  --version 2026-06-30-be-full-moniteur-smoke \
  --limit 3 \
  --manifest-output /tmp/be-full-moniteur-smoke.yaml
```

Smoke extraction:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-06-30-be-full-moniteur-smoke \
  --manifest /tmp/be-full-moniteur-smoke.yaml \
  --source-as-of 2026-06-30 \
  --allow-incomplete
```

Smoke result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `regulation` | 3 | 10 | complete |

Full historical manifest command:

```bash
uv run --extra dev axiom-corpus-ingest discover-belgian-moniteur \
  --start-date 1924-01-01 \
  --end-date 2026-06-30 \
  --version 2026-06-30-be-full-moniteur \
  --manifest-output manifests/be-full-moniteur.yaml
```

Full extraction command:

```bash
uv run --extra dev axiom-corpus-ingest extract-belgian-eli \
  --base data/corpus \
  --version 2026-06-30-be-full-moniteur \
  --manifest manifests/be-full-moniteur.yaml \
  --source-as-of 2026-06-30 \
  --allow-incomplete
```

Notes:

- The full 1924-current crawl is intentionally separate from this smoke run; it
  should run as a long backfill job and may produce a large generated manifest.
- `article.pl` pages are the authoritative original Moniteur publication
  snapshots. Any `Justel` link discovered from an article page remains recorded
  as a consolidated locator.
- Jurisdiction inference is conservative. Brussels ordinances and obvious
  Brussels/Walloon/Flemish/French-community/German-community authority strings
  are tagged separately; ambiguous sources stay under `be`.
