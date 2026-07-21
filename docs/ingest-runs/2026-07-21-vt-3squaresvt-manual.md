# Vermont 3SquaresVT manual ingest

The Vermont Department for Children and Families publishes the 3SquaresVT
benefits rules manual as 32 official HTML chapters. The live table of contents
contains Manual Updates plus numbered chapters 100 through 3100, and the latest
manual update is dated July 1, 2026.

The live TOC inserts 1500 Resources before 1600 Income. The prior manifest had
corrected the displayed titles but retained the old one-step numbering in the
last 16 source IDs and citation paths. This ingest aligns those identifiers with
the current official chapter numbers before running the corpus pipeline. No
provision rows were hand-authored:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-vt-3squaresvt-manual \
  --manifest manifests/us-vt-3squaresvt-manual.yaml
```

Result:

- 32 retained official HTML chapter sources
- 32 document provisions and 879 structured block provisions
- 911 inventory entries matched to 911 provisions
- zero missing, extra, or duplicate citations
- complete coverage

The signed ingest manifest authenticates every retained HTML file and all
generated inventory, provision, and coverage artifacts. Focused tests pin a
compact aggregate digest of all 32 source files, chapter-number alignment,
latest update evidence, generated hierarchy, and coverage.
