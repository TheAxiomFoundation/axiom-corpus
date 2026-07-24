# Oregon 2026 personal-income-tax session laws

This scope preserves three official chaptered publications from the Oregon
Legislative Assembly that carry tax-year-2026 personal-income-tax law not yet
incorporated into the 2025 Edition of the Oregon Revised Statutes:

- [Oregon Laws 2026, chapter 142 (SB 1507)](https://www.oregonlegislature.gov/bills_laws/lawsstatutes/2026orLaw0142.pdf),
  approved April 9, 2026; and
- [Oregon Laws 2026, chapter 50 (HB 4084)](https://www.oregonlegislature.gov/bills_laws/lawsstatutes/2026orLaw0050.pdf),
  approved March 31, 2026; and
- [Oregon Laws 2026, chapter 75 (SB 1510)](https://www.oregonlegislature.gov/bills_laws/lawsstatutes/2026orLaw0075.pdf),
  approved March 31, 2026. The manifest also records the official
  [enrolled SB 1510-A](https://olis.oregonlegislature.gov/liz/2026R1/Downloads/MeasureDocument/SB1510)
  page as its legal-authority provenance.

Chapter 142 sections 2, 5, and 7 establish Oregon additions for tax-year-2026
federal passenger-vehicle-loan interest, qualified-small-business-stock gain,
and bonus depreciation. Section 3 changes the refundable earned income credit
from 9 to 14 percent, or from 12 to 17 percent for a taxpayer with a dependent
under age three. Sections 12 through 14 establish the nonrefundable new-jobs
credit, its per-job and statewide limits, carryforward, and 2026 through 2031
applicability. The chaptered publication's endnote identifies sections 2 and 7
as the subjects of an April 2026 referendum petition; the retained PDF
preserves that legal-status notice verbatim.

Chapter 50 section 16 supplies the final operative new-jobs-credit language. It
amends chapter 142 section 12 to restrict the credit to taxpayers engaged
primarily in a qualified industry and to jobs created in a qualified industry.
It defines the covered industry categories and adds corresponding certification
and rulemaking requirements.

Chapter 75 sections 9 through 12 extend Oregon's elective pass-through business
alternative income tax and corresponding member credit through tax years
beginning before January 1, 2028. They also permit an entity overpayment to be
credited against estimated tax for the following tax year.

The generic official-document adapter snapshots both complete PDFs and emits a
structural document root plus one body-bearing `/document-1` child for each
act:

- `us-or/statute/session-laws/2026/sb1507`
- `us-or/statute/session-laws/2026/sb1507/document-1`
- `us-or/statute/session-laws/2026/hb4084`
- `us-or/statute/session-laws/2026/hb4084/document-1`
- `us-or/statute/session-laws/2026/sb1510`
- `us-or/statute/session-laws/2026/sb1510/document-1`

The retained chapter 142 PDF has SHA-256
`db9c1057f6a67d5cb5416825614192f040e70a6b424c96723d7f2769d21c40cb`.
The retained chapter 50 PDF has SHA-256
`f3e11dedf65f2d079f3f30865675d0da5f495ea864dcc52c686e9a99f72c83a3`.
The retained chapter 75 PDF has SHA-256
`0e323352cafe8a27bb75194f2185ff7b58dcb1603ff6986e9acebfb18a20f419`.
Coverage is complete at six inventory citations and six normalized
provisions, with no missing, extra, or duplicate citations. A fresh extraction
after staging reproduced both PDFs and all generated artifacts byte for byte.

Artifacts are generated without publication or database loading:

```bash
axiom_with_corpus_ingest_key uv run --extra dev axiom-corpus-ingest \
  extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-or-pit-session-laws \
  --manifest manifests/us-or-2026-pit-session-laws-official-documents.yaml
```

The protected wrapper supplies signing material only to the ingest process.
Private signing material is neither printed nor stored in the repository.
Release selection, publication, database loading, and RuleSpec changes remain
separate reviewed steps.
