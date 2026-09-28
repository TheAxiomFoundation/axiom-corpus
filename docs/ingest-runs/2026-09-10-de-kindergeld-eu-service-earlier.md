# Earlier EU programme instruments referenced by continuation rules

This capture retains four complete original German Official Journal texts:

- Regulation (EU) No 375/2014: 17 pages, OJ L 122/1–17, 24 April 2014.
- Decision No 1719/2006/EC: 15 pages, OJ L 327/30–44, 24 November 2006.
- Decision No 1720/2006/EC: 24 pages, OJ L 327/45–68, 24 November 2006.
- Decision No 1298/2008/EC: 16 pages, OJ L 340/83–98, 19 December 2008.

The official EUR-Lex PDFs match the SHA-256 values recorded in the source
manifest and audit. Native extraction retains each complete document as one
content row and a document root: eight rows from four PDFs, covering 72 pages.
Every page has extractable text. Act headings, publication/page identities and
final annex boundaries were inspected. No source body or generated row was
manually edited. The original expression dates are not a claim of current
consolidation or applicability to a 2025 child-benefit case.

The Kindergeld source review discovered these references in Regulation2021/888
Articles32–33 and Regulation1288/2013 Article37. The consumer retains all four
as pending supplemental022–025. This capture does not decide their bearing or
exclude them based on age; programme scope, amendments, continuation conditions
and historical applicability require source-bound legal review. Capture QA is
not a legal review of all 72 pages. No executable module or certified claim.

Reproduce using the existing native adapter:

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-10-de-kindergeld-eu-service-earlier --manifest manifests/de-kindergeld-eu-service-earlier.yaml
```

The additive release preserves all 47 preceding DE scopes and adds this scope:
48 scopes and 9,876 provision rows. Publication and serving activation remain
separate; this work does not activate serving.
