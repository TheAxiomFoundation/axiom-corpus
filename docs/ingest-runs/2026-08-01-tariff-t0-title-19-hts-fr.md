# US tariff T0: Title 19 spine, USITC HTS snapshots, and Federal Register instruments

This source-first scope retains the federal authority needed for the US tariff
encoding lane (rulespec-us#1190, oracle program axiom-oracles#444): the Title
19 statutory spine, four full-revision USITC Harmonized Tariff Schedule (HTS)
JSON snapshots straddling both 2026 tariff regime boundaries, the HTS Revision
14 General Note 3 and Chapter 99 texts, and the operative Federal Register
instruments.

## Regime timeline the snapshots straddle

- **2026-02-24**: IEEPA-based tariffs terminate; the section 122
  balance-of-payments surcharge (10 percent, HTS heading 9903.03.01 with
  exemptions 9903.03.02–9903.03.11, U.S. note 2(aa) to subchapter III of
  chapter 99) takes effect. HTS Revision 3 (effective 2026-02-12) is the last
  pre-boundary edition; Revision 4 (effective 2026-02-25) is the first
  post-boundary edition.
- **2026-07-24**: the 150-day section 122 window ends; the Section 301
  forced-labor country tiers take effect (codified in Revision 13, effective
  2026-07-28, as headings 9903.05.20–9903.05.84 with product exemptions
  9903.05.85–9903.05.92 and country exemptions 9903.06.01–9903.06.21 under
  U.S. note 52, plus the Brazil Section 301 headings 9903.05.01–9903.05.09
  under U.S. note 50). Revision 12 (effective 2026-07-21) is the last
  pre-boundary edition; Revision 14 (effective 2026-07-31, current) carries
  the further modifications effective 2026-07-31 and is the operative
  post-boundary edition retained here. Revision 13 is intentionally skipped:
  no oracle grid date falls inside its 2026-07-28..2026-07-30 window.

Revision effective windows come from the official `hts.usitc.gov`
release list (`reststop/releaseList`): Rev3 02/12–02/25, Rev4 02/25–04/08,
Rev12 07/21–07/28, Rev13 07/28–07/31, Rev14 07/31–current.

## Scopes in this run

### 1. Title 19 statutory spine (`us/statute`, version `2026-08-01-tariff-title-19-spine-title-19`)

Official House USLM XML at release point PL 119-102 (`xml_usc19@119-102.zip`,
retained source `uslm/usc19.xml`, SHA-256
`cd21e6796f9f0baa403d21a37a0a2d70ecfedae92b879e1b7b06738a67591c67`,
14,475,888 bytes). Sections: 19 U.S.C. 1202 (HTS reference; heading-only body
is expected — the schedule itself is not reproduced in the Code), 1401a
(customs value), 1321 (de minimis), 1862 (section 232), 2411 (section 301),
2251 (section 201), 2132 (section 122). 325 subsection-level provisions,
complete coverage.

### 2. USITC HTS full-revision snapshots (`us/statute`, versions `2026-08-01-usitc-hts-2026-rev{3,4,12,14}`)

Reproduced by `scripts/repro/us_hts_tariff_snapshots.py` from pinned official
bytes. Every snapshot is the Internet Archive Wayback Machine capture of the
official USITC static URL
`https://www.usitc.gov/sites/default/files/tata/hts/hts_2026_revision_{N}_json.json`
(the live host is access-controlled; the Wayback captures are of the official
URL itself, fetched server-side by the Archive). Retained byte-for-byte:

| Revision | Effective | Wayback capture | Bytes | Total rows | Target rows | SHA-256 |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 3 | 2026-02-12 | 20260216170026 | 13,689,892 | 35,722 | 1,783 | `fae12fab3c47b54cfb5db7325478d222409adbcfa8a10812fa2af0d213dff07e` |
| 4 | 2026-02-25 | 20260312220249 | 13,698,812 | 35,733 | 1,794 | `0273ec6e6251479a3fc5056e2ed1d4f737fa7ee0675bc37c122364cc7a5732a3` |
| 12 | 2026-07-21 | 20260801124018 | 13,535,498 | 35,678 | 1,595 | `c2df18de026f8ba78178a10dff5033b153c7a48fd66b5f218f529c1369fa0c72` |
| 14 | 2026-07-31 | 20260801124009 | 12,630,562 | 35,789 | 1,706 | `a99da87129ebfd71352b9a747b2a36045a45f7f838ce8d4b9b02e157b78392ef` |

Independent cross-verification before pinning: Revisions 3 and 4 are
byte-identical (same SHA-256) to the Yale Budget Lab `hts_archives` mirrors;
Revision 12 (vs the Yale mirror) and Revision 14 (vs the live
`hts.usitc.gov` reststop export) are content-identical on every field after
dropping the static file's extra leading `0101` heading row, null/empty
normalization, and stripping HTML presentation tags (`<i>`, styled `<sup>`)
that the mirrors retain but the static files strip — zero field differences
remain, footnotes and units included.

Normalized rows cover the pilot chapters 72, 76, and 95 plus every `9903.*`
Chapter 99 heading (steel/aluminum section 232, China section 301, IEEPA
residue in Rev3, section 122 surcharge in Rev4/12/14, forced-labor and Brazil
301 tiers in Rev14). Citation paths are `us/statute/hts/{htsno}`; each row
body carries the article description, units, and the official rate-of-duty
columns (1-General, 1-Special, 2) plus footnotes; row metadata retains the
raw fields and the indent-derived ancestor description chain. Rows without an
`htsno` (superior text lines) are not emitted as provisions but their text is
retained in descendants' ancestor chains and in the byte-exact source. Regime
anchors are asserted per revision (for example: no `9903.03.01` in Rev3;
`+ 10%` on `9903.03.01` in Rev4/12; `+ 12.5%` Algeria tier, `+ 25%` Brazil,
and no-op absence checks in Rev12/14).

### 3. HTS Revision 14 General Note 3 and Chapter 99 (`us/statute`, version `2026-08-01-usitc-hts-2026-rev14-notes`)

Release-pinned official PDFs from
`https://hts.usitc.gov/reststop/file?release=2026HTSRev14&filename=...`
(manifest `manifests/us-usitc-hts-2026-rev14-notes.yaml`), page-level blocks:
General Note 3 (Rates of Duty; 8 pages) and Chapter 99 (805 pages), 815 rows
with complete coverage. Chapter 99 carries the U.S. notes the headings
reference: U.S. note 2(aa) and the 9903.03 rate structure (pages 221 ff.),
U.S. note 50 (Brazil; pages 637–638), and U.S. note 52 (forced-labor tiers;
pages 639 ff.). These are Revision 14 expressions (expression date
2026-07-31); the section 122 proclamation's annex text for the same notes as
first proclaimed is TIFF-only in the Federal Register body (see below), so
the Chapter 99 PDF is the retained text source for note language.

### 4. Federal Register instruments (`us/rulemaking`, five versions)

Extracted with `extract-federal-register` from the federalregister.gov API,
full-text bodies plus metadata:

- `2026-08-01-tariff-presdocu-2026-02-25-types-presdocu`: the 2026-02-25
  presidential documents implementing the 2026-02-24 boundary (FR docs
  2026-03824 — the section 122 surcharge proclamation, whose annex is
  TIFF-only as noted; 2026-03829; 2026-03832).
- `2026-08-01-tariff-fl-301-2026-07-28-types-notice-presdocu-term-forced-labor`:
  the forced-labor Section 301 action (2026-15181, USTR notice; 2026-15274).
- `2026-08-01-tariff-brazil-301-2026-07-20-types-notice-presdocu-term-brazil-digital-trade`:
  the Brazil Section 301 action (2026-14542; 2026-14654).
- `2026-08-01-tariff-232-aluminum-2026-07-23-types-presdocu-term-aluminum`:
  the section 232 aluminum modification (2026-14990).
- `2026-08-01-tariff-de-minimis-mail-2026-06-24-types-rule-term-mail-shipments`:
  the de minimis mail-shipments rule (2026-12669) and its non-postal
  companion (2026-12670).

## Downstream

These scopes feed the tariff encodings in `rulespec-us` (`us/statutes/19/...`)
and the `us_tariff` oracle suite in `axiom-oracles`; the four HTS revision
snapshots are the primary oracle comparison surface. New citation paths widen
the pending `us` release cut.
