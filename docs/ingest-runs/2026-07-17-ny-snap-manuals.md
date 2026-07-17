# New York SNAP manuals ingest (2026-07-17)

## Boundary

The official OTDA legal index identifies the SNAP Source Book, and Source Book
Section 10 delegates SNAP employment and work requirements to OTDA's Temporary
Assistance and SNAP Employment Policy Manual. The employment-manual index lists
16 component PDFs: the introduction, sections 385.2 through 385.13, and
appendices A through C. This ingest retains that full 17-document manual
boundary.

Live OTDA PDF requests reset unattended HTTP clients. Each retained file is
therefore an Internet Archive capture of the official OTDA PDF URL. On
2026-07-17 the live official browser views matched the retained captures' page
counts and displayed revisions. The manifest pins every archive timestamp,
source hash, byte count, page count, and revision.

## Extraction

Command:

```text
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-official-documents --base data/corpus --version 2026-07-17-ny-snap-manuals --manifest manifests/us-ny-snap-manual.yaml
```

The encoder's official-document extractor produced 340 rows from 878 retained
pages: 17 document roots, all 21 top-level Source Book sections, and all 302
Employment Policy Manual pages. Coverage is complete at 340 of 340 with no
missing, extra, or duplicate citation paths. Employment pages use stable `p-N`
segments instead of increasing the corpus's legacy `page-N` ratchet.

Aggregate generated-artifact digest after the successful extraction:

```text
04e93169a306830c3833e39096599baedc8aa7b20a82b5b5adfe5503efe9052b
```

No corpus rows or retained source files were authored or edited manually. The
superseded source-less Source Book scope is removed only after this replacement
scope is committed and signed, with its removal recorded in a signed tombstone.
