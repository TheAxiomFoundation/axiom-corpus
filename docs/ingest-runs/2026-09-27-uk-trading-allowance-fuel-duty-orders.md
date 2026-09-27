# UK trading allowance and fuel duty reduction orders ingest

Two provisions behind the Autumn Budget 2026 PolicyEngine-UK parity work were
not in the corpus, so the supervised encoder could not cite them:

- the trading allowance (rulespec-uk#348), and
- the dated fuel duty reduction schedule (rulespec-uk#349).

This run captures both from legislation.gov.uk CLML. It writes no RuleSpec.

## Scopes

| Scope | Provisions | Coverage |
| --- | --- | --- |
| `uk/statute/2026-09-27-uk-trading-allowance` | 19 | complete: 19 sources, 19 matched, 0 missing, 0 extra |
| `uk/statute/2026-09-27-uk-fuel-duty-reduction-orders` | 2 | complete: 2 sources, 2 matched, 0 missing, 0 extra |
| `uk/regulation/2026-09-27-uk-fuel-duty-reduction-orders` | 18 | complete: 18 sources, 18 matched, 0 missing, 0 extra |

Citations:

- Income Tax (Trading and Other Income) Act 2005 (c. 5), Part 6A Chapter 1
  ("Trading allowance"), ss. 783A, 783AA, 783AB, 783AC, 783AD, 783AE, 783AF,
  783AG, 783AH, 783AI, 783AJ, 783AK, 783AL, 783AM, 783AN, 783AO, 783AP, 783AQ
  and 783AR. These are all the sections in the chapter: the chapter element in
  `https://www.legislation.gov.uk/ukpga/2005/5/part/6A/data.xml` (fetched
  2026-09-27) holds these 19 sections and no others. Chapter 2 (property
  allowance, ss. 783B-783BQ) is not in scope.
- Excise Duties (Surcharges or Rebates) Act 1979 (c. 8), ss. 1 and 2, the
  enabling power for the orders.
- SI 2022/365 arts 1-4; SI 2023/329 arts 1-2; SI 2024/300 arts 1-2;
  SI 2025/228 arts 1-2; SI 2026/164 arts 1, 2, 3, 4 and 8; SI 2026/555
  arts 1-3.

## Commands

The existing CLML path of `extract-uk-legislation` handles article citations
(`uksi/<year>/<number>/article/<n>`), so no extractor change was needed.
Both runs used `--as-of 2026-09-27 --expression-date 2026-09-27`, the fetch
date.

```bash
uv run --extra dev axiom-corpus-ingest extract-uk-legislation \
  --base data/corpus --version 2026-09-27-uk-trading-allowance --source clml \
  --citation ukpga/2005/5/section/783A --citation ukpga/2005/5/section/783AA \
  --citation ukpga/2005/5/section/783AB --citation ukpga/2005/5/section/783AC \
  --citation ukpga/2005/5/section/783AD --citation ukpga/2005/5/section/783AE \
  --citation ukpga/2005/5/section/783AF --citation ukpga/2005/5/section/783AG \
  --citation ukpga/2005/5/section/783AH --citation ukpga/2005/5/section/783AI \
  --citation ukpga/2005/5/section/783AJ --citation ukpga/2005/5/section/783AK \
  --citation ukpga/2005/5/section/783AL --citation ukpga/2005/5/section/783AM \
  --citation ukpga/2005/5/section/783AN --citation ukpga/2005/5/section/783AO \
  --citation ukpga/2005/5/section/783AP --citation ukpga/2005/5/section/783AQ \
  --citation ukpga/2005/5/section/783AR \
  --as-of 2026-09-27 --expression-date 2026-09-27

uv run --extra dev axiom-corpus-ingest extract-uk-legislation \
  --base data/corpus --version 2026-09-27-uk-fuel-duty-reduction-orders --source clml \
  --citation ukpga/1979/8/section/1 --citation ukpga/1979/8/section/2 \
  --citation uksi/2022/365/article/1 --citation uksi/2022/365/article/2 \
  --citation uksi/2022/365/article/3 --citation uksi/2022/365/article/4 \
  --citation uksi/2023/329/article/1 --citation uksi/2023/329/article/2 \
  --citation uksi/2024/300/article/1 --citation uksi/2024/300/article/2 \
  --citation uksi/2025/228/article/1 --citation uksi/2025/228/article/2 \
  --citation uksi/2026/164/article/1 --citation uksi/2026/164/article/2 \
  --citation uksi/2026/164/article/3 --citation uksi/2026/164/article/4 \
  --citation uksi/2026/164/article/8 \
  --citation uksi/2026/555/article/1 --citation uksi/2026/555/article/2 \
  --citation uksi/2026/555/article/3 \
  --as-of 2026-09-27 --expression-date 2026-09-27
```

## Provenance

Every source is the legislation.gov.uk CLML `data.xml` for one provision,
fetched on 2026-09-27. Each inventory item records the provision's source URL
and the SHA-256 of the archived XML; all 39 hashes were rechecked against the
files. The extractor rewrites editorial `key-<hex>` anchors inside tags to
`key-a<N>` placeholders in the archived copy. No raw anchors remain in the
39 files.

## Which version of each order

legislation.gov.uk serves revised text only for instruments its editors have
revised. At the default URL on 2026-09-27:

- SI 2023/329, SI 2024/300, SI 2025/228 and SI 2026/555 have no revised
  version. The default `data.xml` redirects to `/made/data.xml`, and each row's
  `source_url` ends in `/made`. For these the made text is the operative text.
- SI 2022/365 and SI 2026/164 are revised. The default URL serves the current
  version (`dct:valid` 2026-06-15; versions listed: SI 2022/365 made,
  2022-03-23 to 2026-06-15; SI 2026/164 made, 2026-03-23, 2026-06-15). These
  scopes hold that current text.

The current SI 2026/164 text reflects SI 2026/555 art. 2:

- art. 1(2) reads "ending with 31st December 2026";
- art. 1(3) is omitted (". . ." in the text);
- art. 1(4) reads "beginning with 1st January 2027 and ending with 28th
  February 2027";
- art. 3 reads "continues in force until the end of 31st December 2026";
- art. 4 is omitted (the row body is only the omission dots), as are arts 5-7.

The current SI 2022/365 text reflects SI 2026/555 art. 3. In art. 4 Table C,
rows (b), (c), (f) and (g) read 9.96 in column (C) and 0.0648 in column (D).

The heading substitution in SI 2026/555 art. 2(5) ("1st January 2027" in the
headings of arts 8-11) is also applied on legislation.gov.uk. The corpus row
does not carry it, because the extractor gives provisions a structural heading
("Article 8") and does not copy the P1group title. Art. 1(4), which is in the
corpus, states the same period.

## Outstanding effects

Each ITTOIA 2005 source lists one unapplied effect. It comes from asc/2026/7
and inserts "s. 168(6)(e) and word", so it touches s. 168, not Part 6A. The
1979 Act and order sources list none.

## Spot checks

- ITTOIA s. 783AD: "For the purposes of this Chapter, an individual's trading
  allowance for a tax year is £1,000."
- ITTOIA s. 783AI(2): "Step 1 Calculate the total of all the amounts which
  would, apart from this Chapter, be brought into account as a receipt in
  calculating the profits of the trade for the tax year." and "Step 2 Subtract
  the deductible amount." The third list item in the source is "...", which
  the body keeps.
- SI 2022/365 art. 3 Table A: "| (a) | Unleaded petrol | 0.5795 | 8.63 |
  0.5295 |".
- SI 2026/164 art. 8 Table D: "| (a) | Unleaded petrol | 0.5795 | 3.45 |
  0.5595 |".
- SI 2026/555 art. 2: "In article 1— / in paragraph (2), for “31st August
  2026” substitute “31st December 2026”; / omit paragraph (3); / in paragraph
  (4), for “1st December 2026” substitute “1st January 2027”. / In article 3,
  for “31st August 2026” substitute “31st December 2026”. / Omit articles 4
  to 7. / In articles 8 to 11, in each of the headings, for “1st December 2026”
  substitute “1st January 2027”."

Every body was also compared with the provision's legislation.gov.uk HTML page,
a separate rendering from the CLML the extractor read. Each non-table body line
and each table cell was checked as a whitespace-normalized substring of the
page text. Before comparison, the HTML-only apparatus was removed from both
sides: `[F<n>` amendment markers, `M<n>` marginal-citation markers, square
brackets and footnote references. All 39 provisions passed. A negative
control on the same pages rejected "0.5296", "8.64", "ending with 31st August
2026" and "beginning with 1st December 2026".

## Extractor behaviour an encoder should know

These are properties of the existing UK CLML extractor, not of this run:

- Bodies omit the provision numbers: "(1)", "(a)" and the article number.
- Table captions ("Table A", "Table D") are not carried. Tables are rendered as
  Markdown after the provision's text, in source order. SI 2022/365 art. 3 and
  SI 2026/164 art. 8 each carry two tables: the per-litre table (A or D) first,
  then the road fuel gas table (B or E).
- The source text itself contains the "[" and "]" in 1979 Act s. 2(7) and the
  missing opening quote in SI 2026/555 art. 3(b) (`substitute 0.0648”`). They
  are kept verbatim.

## Correction to an earlier note

`docs/ingest-runs/2026-07-07-uk-indirect-taxes.md` says the temporary fuel
duty cut "is set by annual Budget resolution". The text ingested here shows a
different mechanism. 1979 Act s. 1(2): "The Treasury may, by an order ...
provide for an adjustment— of any liability to such a duty ... by the addition
to or deduction from the amount payable or allowable of such percentage, not
exceeding 10 per cent, as may be specified in the order." The made SI 2022/365
(`https://www.legislation.gov.uk/uksi/2022/365/made/data.xml`; its preamble is
not a corpus row) recites "in exercise of the powers conferred by sections 1(2)
and 2(3)" of that Act. Its art. 3 adjusts the liability "in accordance with
Table A ... by the deduction from the amount payable of the percentages
specified in column (C)", with unleaded petrol at 0.5795 before and 0.5295
after an 8.63 percentage deduction.

## Citation-path ratchet

The ITTOIA section numbers carry uppercase letters, so the new paths count
toward the `uppercase_segments` family in `scripts/validate_citation_paths.py`.
`uk/statute/ukpga/2005/5/783A` already exists (scope
`2026-06-01-uk-frs-microsim`). The other 18 paths, 783AA to 783AR, are new
unique paths, so the baseline in `schema/citation-path.v1.json` rises from
16280 to 16298. The validator's live count on this branch is 16298.

## After merge

- Merge with a merge commit, never squash. The signed ingest manifests record
  the data commit, which must stay an ancestor of `main`.
- The encoder can cite these scopes only after two more steps. First, cut a UK
  release that carries them: the next `manifests/releases/uk-rulespec-*.json`
  after `uk-rulespec-2026-09-07`. Second, rebind the rulespec-uk toolchain to
  that release.
