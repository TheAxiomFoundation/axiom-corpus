# IRS Optional State and Local Sales Tax Tables, tax year 2021

Follow-on to `2026-09-24-irs-optional-sales-tax-tables-ty2022-2025`
([docs](2026-09-24-irs-optional-sales-tax-tables.md)). It adds TY2021 with the
same four `single_block` slices, the same text order and the same extractor, so a
rulespec encoding can cite every tax year from 2021 to 2025. These are the tables
the Secretary prescribes under 26 U.S.C. 164(b)(5)(H)(i)(II).

## Source

| | |
| --- | --- |
| URL | https://www.irs.gov/pub/irs-prior/i1040sca--2021.pdf |
| sha256 | `dabdcc727779b89caa2969cc5274b716ce7588855e1d8605bd81e195a6ef333d` |
| Bytes | 702,617 |
| Pages | 18 (`pdfinfo`) |
| HTTP Last-Modified | Thu, 06 Jan 2022 03:10:56 GMT |
| PDF ModDate | 2022-01-04 |
| Retrieved | 2026-09-24 |

## Slices

| Citation path (`us/form/irs/ty2021/…`) | PDF pages | Window |
| --- | --- | --- |
| `i1040sca-line-5a-general-sales-taxes` | 3-7 | from `^Line 5a$` to before `^Line 5b$`, stream order |
| `i1040sca-optional-state-sales-tax-tables` | 14-17 | `sort_text: true` |
| `i1040sca-optional-local-sales-tax-table-selector` | 18 | from `^Which Optional Local Sales Tax Table Should I Use\?` to before `^2021 Optional Local Sales Tax Tables$`, stream order |
| `i1040sca-optional-local-sales-tax-tables` | 18 | from `^2021 Optional Local Sales Tax Tables$`, `sort_text: true` |

Each slice has a root and a `/document-1` child: 8 provisions, coverage 8/8.
The TY2021 table and selector pages sit one page later than TY2022's (the TY2021
PDF has 18 pages); the line 5a slice is pages 3-7 in both years.
The manifest was derived from the TY2022 entries of the TY2022-2025 manifest by a
script that changes only year-specific values and asserts that no other field
still names 2022.

## Extraction notes

- **Wyoming block.** As in TY2022-2025, the footnote legend sits beside the
  Wyoming rows, so the position sort places some Wyoming rows on legend lines.
  In TY2021 one token is fused: the `$100,000 $120,000` row follows footnote 5
  directly, as `... the 4.60% state$100,000 $120,000 555 606 637 661 680 705
  sales tax rate ...`. The row's tokens are intact. A proof excerpt that starts
  at `$100,000` on that line is not token-bounded; quote from `state$100,000`
  or cite another row.
- **No base-rate caption.** TY2021 prints no "(Based on a local sales tax rate
  of 1%)" caption on the local tables, like TY2022 and TY2023. The local-table
  body starts with the title `2021 Optional Local Sales Tax Tables`.
- The selector prints `Wyoming or Yate` (not `Yates`) in the New York Table B
  county list, in the PDF itself.

## Fidelity checks

- Every state and local cell was parsed from the same PDF two independent ways
  (poppler `pdftotext -layout`, and pdfplumber word boxes): 5,700 cells, zero
  disagreements. The same two parsers agree with the TY2022-2025 scope on all of
  its years.
- The digests pinned in `tests/test_us_irs_optional_sales_tax_tables.py` for
  TY2021 come from that independent parse; the digest code reproduces the
  already-pinned TY2022-2025 digests exactly. The committed TY2021 bodies
  re-parse to the pinned digests.
- The same consistency checks as TY2022-2025 hold for TY2021: states footnoted
  2 equal worksheet line 2's list less Alaska; states footnoted 4 equal the
  "skip lines 2 through 5" list; tables are non-decreasing in family size and
  in income; Local Table D is within 1 of 0.25 × the New York table; the body
  keeps every PDF token of its window (PyMuPDF 1.26.7).
- Spot cell: Texas, $80,000-$90,000, family size 2 = 851. Texas, "$300,000 or
  more": `1777 1999 2141 2248 2335 2454`.

## What changed from TY2021 to TY2022 (parsed from both PDFs)

- State rates: only New Mexico, 5.1250% → 5.0620%.
- Footnote 5 prints Nevada's rate as 4.60% (TY2021) and 4.6000% (TY2022).
- Worksheet line 2 lists the same 15 local-table states in both years
  (Alabama and Kansas join in TY2023).
- The local-table selector reassigns localities between tables, for example
  Arizona (TY2021 Table A is "Mesa, Phoenix, Tucson"; TY2022 Table C is
  "Tempe") and Colorado (Arapahoe County and Aurora move from Table A to
  Table B).

## Commands

```bash
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-09-24-irs-optional-sales-tax-tables-ty2021 \
  --manifest manifests/us-irs-optional-sales-tax-tables-ty2021.yaml
uv run --extra dev pytest -q tests/test_us_irs_optional_sales_tax_tables.py
```

## Not done here

No R2 upload, Supabase load, release selector, release signature or activation.
A release that serves TY2021 must select this scope alongside
`2026-09-24-irs-optional-sales-tax-tables-ty2022-2025`.
