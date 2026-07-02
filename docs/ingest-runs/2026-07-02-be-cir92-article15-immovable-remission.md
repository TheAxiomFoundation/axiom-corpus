# Belgium CIR 1992 Article 15 Immovable Remission Ingest

Run date: 2026-07-02

Purpose:

- Snapshot the current consolidated CIR 1992 Article 15 text needed for
  non-Flemish immovable-withholding remission/moderation under Article 257 item
  4.
- Preserve the upstream source distinction: Moniteur/Justel ELI remains the
  legal locator for CIR 1992, while the FisconetPlus consolidated PDF is the
  current operative text source because the Justel consolidation is suspended.

Primary source:

- `https://finances.wallonie.be/files/NOSTRA/textes%20legaux/code%20des%20impots%20sur%20le%20revenu%20-%20exercice%202022.pdf`
- Legal authority locator:
  `https://www.ejustice.just.fgov.be/eli/loi/1992/04/10/1992041050/moniteur`
- Related property-tax citation already in corpus:
  `be/statute/fisconetplus/cir92/revenus-2025/page-446` for Articles 256 and
  257 item 4.

Command:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-02-be-cir92-article15-immovable-remission \
  --manifest manifests/be-cir92-article15-immovable-remission-official-documents.yaml
```

Result:

| Jurisdiction | Document class | Source files | Provisions | Coverage |
|---|---:|---:|---:|---:|
| `be` | `statute` | 1 | 744 | complete |

The official-document extractor snapshots and extracts the full consolidated
CIR 92 PDF for this source. The manifest identifies Article 15 as the immediate
target, and the generated provision set also preserves the related Article 256
and Article 257 item 4 pages needed for the immovable-withholding remission
bridge.

Key citation paths:

- `be/statute/fisconetplus/cir92/revenus-2025/page-58`
- `be/statute/fisconetplus/cir92/revenus-2025/page-59`
- `be/statute/fisconetplus/cir92/revenus-2025/page-446`
