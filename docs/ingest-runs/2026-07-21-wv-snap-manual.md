# West Virginia SNAP manual ingest

## Source boundary

The West Virginia Bureau for Family Assistance publishes the current Income
Maintenance Manual as one integrated PDF. The retained official response is
`Binder4 - Effective 07-01-2026_0.pdf`, effective July 1, 2026. It is exactly
24,621,268 bytes with SHA-256
`551ed2bcc677262e9bcbc2b28d1474d27b6734d89ad07b1cb5da829dc2c4bb3f`.
All 2,275 PDF pages contain native extractable text, so the standard PDF-page
extractor was used without OCR or custom segmentation.

The PDF's bookmarks cover the introduction, Chapters 1 through 29, a separate
Chapter 4 appendices range, and the final acronyms/forms/glossary range. The
current asset rule is section 5.4, replacing the old section 11.3 source retained
by the source-less scope. Section 5.4 states the current SNAP limits of $3,000,
or $4,500 when an assistance-group member is at least 60 or disabled. Chapters
16 and 17 retain the specific SNAP and SNAP E&T material.

The manual still prints the SNAP soda restriction in sections 1.4.20 and 16.3.
The separate official July 10, 2026 policy notice immediately discontinues that
restriction. It is retained as its own signed HTML scope, using the article-body
selector and producing one document row plus one content block.

This corpus does not yet retain the underlying federal and state authorities,
the USDA directive, or the federal court order described in the July 10 notice.
The landing page's 2014 archive ZIP at
`https://dhhr.wv.gov/bfa/policyplans/Documents/West%20Virginia%20Income%20Maintenance%20Manual%20-%202014.zip`
is dead. The manual also directs readers to the broken change-search hostname at
`http://www.DoHS.wv.gov/bcf/Services/familyassistance/Pages/IMMSearch.aspx`.

## Generated scopes

No retained source or provision row was authored by hand. The repository's
official-document extractor fetched and generated both scopes through the
shared project environment:

```bash
PYTHONPATH=src \
UV_PROJECT_ENVIRONMENT=/Users/pavelmakarchuk/axiom-corpus-uc/.venv \
uv run --no-sync python -m axiom_corpus.corpus.cli \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-wv-income-maintenance-manual \
  --manifest manifests/us-wv-manuals.yaml

PYTHONPATH=src \
UV_PROJECT_ENVIRONMENT=/Users/pavelmakarchuk/axiom-corpus-uc/.venv \
uv run --no-sync python -m axiom_corpus.corpus.cli \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-21-wv-snap-healthy-choices-overlay \
  --manifest manifests/us-wv-snap-healthy-choices-overlay.yaml
```

The PDF scope contains 2,276 rows: one document and 2,275 page provisions. The
HTML overlay contains two rows: one document and one content block. Both scopes
have complete coverage with no missing, extra, or duplicate citation paths.

The source-less `2026-05-27-wv-manuals` inventory, provisions, and coverage are
removed only after both replacements are generated, committed, and signed. A
separate signed ingest tombstone authenticates exactly those three deletions.
