# IRS Optional State and Local Sales Tax Tables, tax years 2022-2025

This intake preserves the tables the Secretary prescribes under 26 U.S.C.
164(b)(5)(H) for tax years 2022, 2023, 2024 and 2025, as printed in each year's
official Instructions for Schedule A (Form 1040), together with the line 5a
instructions and the State and Local General Sales Tax Deduction Worksheet that
apply them.

Statutory anchor: `us/statute/26/164` in scope
`2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup`, whose
(b)(5)(H)(i) lets the taxpayer elect to deduct "(I) the amount determined under
this paragraph (without regard to this subparagraph) with respect to motor
vehicles, boats, and other items specified by the Secretary, and (II) the amount
determined under tables prescribed by the Secretary with respect to items to
which subclause (I) does not apply."

Until now the corpus had none of the TY2022-TY2024 instructions. The TY2025 HTML
edition (`us/form/irs/ty2025/i1040sca`, scope `2026-09-10-tax-irs-forms-ty2025`)
carries the TY2025 tables flattened into one paragraph inside `block-53`
(heading "Line 18"), where row boundaries are lost.

## Sources

| Tax year | URL | Bytes | SHA-256 | Last-Modified | PDF ModDate |
| --- | --- | --- | --- | --- | --- |
| 2022 | <https://www.irs.gov/pub/irs-prior/i1040sca--2022.pdf> | 688,971 | `7fab0861b94e075f9e60f8b8c9e23b234e5b0dccae37b7025847e9806e3e8f08` | 2023-01-04 | 2023-01-03 |
| 2023 | <https://www.irs.gov/pub/irs-prior/i1040sca--2023.pdf> | 690,626 | `63a8e9171defdfc6aa7380d9c4e4f168984f8a50cb4352fe7d62994fb455428e` | 2024-01-06 | 2024-01-04 |
| 2024 | <https://www.irs.gov/pub/irs-prior/i1040sca--2024.pdf> | 565,727 | `a8d762028c317629e841e4b600a1f6d55b41a9b778bce7e07726205187d3a599` | 2024-12-21 | 2024-12-20 |
| 2025 | <https://www.irs.gov/pub/irs-prior/i1040sca--2025.pdf> | 594,250 | `b0999b12d9dc4b13868501a9c1879011c00d2fc035f13a1391251d355a6242c8` | 2025-12-18 | 2025-12-18 |

Retrieved 2026-09-24. The TY2025 file is byte-identical to the current
`https://www.irs.gov/pub/irs-pdf/i1040sca.pdf`.

## Slices

`manifests/us-irs-optional-sales-tax-tables-ty2022-2025.yaml` captures each PDF
as four `single_block` slices with `page_windows`. Every slice of a year fetches
the same URL, and its four retained source files carry the same SHA-256.

| Citation path (`us/form/irs/ty<YYYY>/…`) | TY2022 | TY2023 | TY2024 | TY2025 | Text order |
| --- | --- | --- | --- | --- | --- |
| `i1040sca-line-5a-general-sales-taxes` | 3-7 | 3-7 | 3-6 | 3-6 | stream |
| `i1040sca-optional-state-sales-tax-tables` | 13-16 | 13-16 | 12-15 | 13-17 | position sort |
| `i1040sca-optional-local-sales-tax-table-selector` | 17 | 17 | 16 | 18 | stream |
| `i1040sca-optional-local-sales-tax-tables` | 17 | 17 | 17 | 18 | position sort |

Each root carries one body-bearing child, `<root>/document-1`; coverage is
32/32. `expression_date` is January 1 of the tax year.

- The line 5a slice runs from the `Line 5a` heading up to (not including) the
  `Line 5b` heading. It holds the income-or-sales-tax election, actual expenses,
  the optional-table method, the worksheet (lines 1-8), the instructions for
  the worksheet, and the part-year, multi-state and rate-change rules.
- The selector and the local tables share one page in TY2022, TY2023 and
  TY2025. The selector window stops before the line
  `<YYYY> Optional Local Sales Tax Tables`; the local-table window starts at it.
  Neither body carries the other's rows. In TY2025 the page's methodology
  paragraph ("The optional sales tax tables have historically been
  constructed…") appears in both: stream order puts it before the tables
  heading and the position sort puts it after the rows. In TY2024 the selector
  and the tables are on separate pages, so the selector window needs no stop
  anchor.

## Extraction choices

Bodies were extracted with PyMuPDF 1.26.7, the `uv.lock` pin, which each slice
records as `text_extractor`.

- **Table slices** use `sort_text: true`, so each printed table row stays on one
  line: the two income bounds, then six values per state (three states per
  block, Wyoming alone). In stream order the same pages come out one cell per
  line (6,130 body lines for the TY2023 state table instead of 346, counting
  the blank lines between pages).
- **Instruction and selector slices** use stream order. On the two-column
  instruction pages a position sort interleaves the columns. On the TY2022
  selector page it also runs the South Carolina county lists together
  ("County,County, ColletonLaurens County, …").
- **Wyoming block.** The footnote legend is printed to the right of the Wyoming
  rows, so the position sort puts note text on the same lines as the row
  values. Two placements move a whole row mid-line:
  - In TY2024 and TY2025 the `$90,000 $100,000` row follows footnote 4's text
    on the line that begins with row `$80,000 $90,000`.
  - In TY2022 and TY2023 the `$100,000 $120,000` row follows the first line of
    footnote 5. In TY2022 the rate and the row's lower bound fuse into one
    whitespace token, `4.6000%$100,000`, so a parser that splits on whitespace
    must separate them.

  All six values of every Wyoming row are present and in order.

The pipeline removes and replaces no words. For every slice, the body's tokens
equal the tokens PyMuPDF 1.26.7 returns for its page window, in the slice's
text order. `test_slice_bodies_keep_every_pdf_token` checks this. It runs only
under PyMuPDF 1.26.7, so CI, which installs a newer PyMuPDF, skips it (the FTB
3514 scope has the same limitation); the other tests read the committed bodies
and run under any version. None of the four PDFs contains `/ActualText`, and
the bodies have no "Bullet" tokens. The repeated lines they do contain (page
column headings, "Any locality that imposes a local sales tax", worked-example
sentences) are printed more than once in the PDFs, at distinct positions, and
poppler's `pdftotext -raw` also reads each repeat.

## Fidelity checks

The table cells were parsed three independent ways before ingestion:

1. **poppler** `pdftotext -layout`, reading block headers (`<State>
   <footnote> <rate>%`) and slicing each income row into 3 × 6 family-size
   columns.
2. **MuPDF** word boxes grouped into lines by baseline.
3. **For TY2025, two further sources:**
   - the irs.gov HTML edition retained in `2026-09-10-tax-irs-forms-ty2025`
     (`table[summary="2025 Optional State Sales Tax Tables"]` and the local
     table);
   - an unrelated extraction of the published 2025 state table (PolicyBench's
     projection audit; it does not cover the local tables).

All methods agree on every cell they cover:

- poppler and MuPDF: 5,244 state-table cells and 456 local-table cells per
  year, 22,800 cells over four years, and every state's footnote markers and
  rate;
- the TY2025 HTML edition: all 5,700 TY2025 cells, rates and footnotes;
- PolicyBench: all 5,244 TY2025 state-table cells.

The corpus bodies were then re-parsed with a whitespace-insensitive token
parser and compared with that ground truth: 0 differences. The tests pin
SHA-256 digests of each year's state grid, header (footnotes and rate) map and
local grids, so any lost, reordered or misread cell fails CI.

## What the tables contain

**State table** (each year):
- 46 jurisdictions: the 50 states and the District of Columbia, minus Alaska,
  Delaware, Montana, New Hampshire and Oregon, which have no state general
  sales tax.
- Alaska appears only in a note beside Wyoming ("Residents of Alaska do not
  have a state sales tax, but should follow the instructions on the next page
  to determine their local sales tax amount").
- 19 income brackets:
  - lower bound inclusive ("At least"), upper bound exclusive ("But less than");
  - $0-$20,000, then $10,000 steps to $100,000, $20,000 steps to $200,000,
    $25,000 steps to $300,000, and "$300,000 or more".
  - The brackets are identical in all four years.
- Six family-size columns: 1, 2, 3, 4, 5 and "Over 5".
- Every table is non-decreasing across family size and across income brackets
  in all four years. This holds for both the state tables and Local Tables A-D.

**Header footnotes:**

| Marker | Meaning | Notes |
| --- | --- | --- |
| 1 | ratio method | |
| 2 | use the local tables | |
| 3 | California table includes the 1.25% uniform local rate | |
| 4 | no local general sales tax | CT, DC, IN, KY, MA, MD, ME, MI, NJ, RI: exactly the worksheet's "skip lines 2 through 5" list |
| 5 | Nevada table includes the 2.25% uniform local rate | |
| 6 | Hawaii's rate is an excise tax | |
| 7 | TY2023 only | New Mexico and South Dakota: "The rate decreased during 2023 so the given rate is an average for the year." |

**Year-to-year differences** (from the parsed tables):
- Alabama and Kansas carry footnote 1 in TY2022 and footnote 2 from TY2023.
  The TY2022 worksheet's line 2 list likewise omits them: 15 states, against
  17 from TY2023. In every year, the footnote-2 states equal the line 2 list
  minus Alaska.
- **Rate changes**, as printed (TY2022 and TY2023 print four decimals, TY2024
  and TY2025 two):
  - New Mexico: 5.0620%, 4.9400%, 4.88%, 4.88%.
  - South Dakota: 4.5000%, 4.3500%, 4.20%, 4.20%.
  - Louisiana: 4.4500%, 4.4500%, 4.45%, 5.00%.
  - Minnesota, Missouri and New Jersey print 6.8750%, 4.2250% and 6.6250% in
    TY2022, 6.8800%, 4.2300% and 6.6300% in TY2023, and 6.88%, 4.23% and 6.63%
    in TY2024 and TY2025.
- **TY2025 construction.** The TY2025 pages state that the IRS built TY2025
  from the TY2024 tables. It adjusted every value by the 2024-to-2025 growth of
  total state general sales and gross receipts tax revenues (adjusted for
  population changes), and adjusted Louisiana's state table for its rate
  increase. The parsed cells show exactly that:
  - every non-Louisiana TY2025 cell is TY2024 × 1.01-1.02 (rounding);
  - Louisiana cells are × 1.140-1.143, which is 5.00/4.45 × about 1.015;
  - Local Table cells are × about 1.01-1.02 (1.0105-1.0204).

**Local tables:**
- TY2024 and TY2025 caption Local Tables A-D "(Based on a local sales tax rate
  of 1%)". The TY2022 and TY2023 PDFs print no such caption.
- In every year, worksheet line 6 multiplies the local-table amount (line 2) by
  the local rate entered on line 3 without the percent sign.
- The local tables have the same 19 brackets and six family-size columns.
- The selector maps state and locality to a table. Local Table D is "just 25%
  of the NY State table".

## Commands

```bash
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-09-24-irs-optional-sales-tax-tables-ty2022-2025 \
  --manifest manifests/us-irs-optional-sales-tax-tables-ty2022-2025.yaml
uv run --extra dev pytest -q tests/test_us_irs_optional_sales_tax_tables.py
```

## Not done here

This PR performs no R2 upload, Supabase load, release selector, release
signature or activation.

A release that serves these slices must select this scope. It does not
collide with `2026-09-10-tax-irs-forms-ty2025`: the new TY2025 paths are
sibling roots (`us/form/irs/ty2025/i1040sca-…`), not children of
`us/form/irs/ty2025/i1040sca`.
