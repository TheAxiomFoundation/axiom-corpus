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
| `uk/regulation/2026-09-27-uk-fuel-duty-reduction-orders` | 26 | complete: 26 sources, 26 matched, 0 missing, 0 extra |

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
- Every article of the six orders: SI 2022/365 arts 1-6; SI 2023/329,
  SI 2024/300 and SI 2025/228 arts 1-2; SI 2026/164 arts 1-11; SI 2026/555
  arts 1-3.

The request named a subset of articles. The subset left out SI 2026/164 art. 9
(the rebate adjustments for 1 January to 28 February 2027, Table F), arts 10
and 11, and SI 2022/365 arts 5 and 6. Arts 10 and 11 and SI 2022/365 arts 5
and 6 adjust fuel substitutes duty and aqua methanol additive or extender
duty. SI 2026/164 art. 1(4) says "Articles 8 to 11 have effect" in that
period, so without them the schedule would stop at 31 December 2026 for
rebated fuels. The scope therefore holds each instrument whole. SI 2026/164
arts 4-7 are omitted in the current text, and their rows hold only the
omission dots.

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
  --citation uksi/2022/365/article/5 --citation uksi/2022/365/article/6 \
  --citation uksi/2023/329/article/1 --citation uksi/2023/329/article/2 \
  --citation uksi/2024/300/article/1 --citation uksi/2024/300/article/2 \
  --citation uksi/2025/228/article/1 --citation uksi/2025/228/article/2 \
  --citation uksi/2026/164/article/1 --citation uksi/2026/164/article/2 \
  --citation uksi/2026/164/article/3 --citation uksi/2026/164/article/4 \
  --citation uksi/2026/164/article/5 --citation uksi/2026/164/article/6 \
  --citation uksi/2026/164/article/7 --citation uksi/2026/164/article/8 \
  --citation uksi/2026/164/article/9 --citation uksi/2026/164/article/10 \
  --citation uksi/2026/164/article/11 \
  --citation uksi/2026/555/article/1 --citation uksi/2026/555/article/2 \
  --citation uksi/2026/555/article/3 \
  --as-of 2026-09-27 --expression-date 2026-09-27
```

## Provenance

Every source is the legislation.gov.uk CLML `data.xml` for one provision,
fetched on 2026-09-27. Each inventory item records the provision's source URL
and the SHA-256 of the archived XML; all 47 hashes were rechecked against the
files. The archived XML is not byte-identical to what legislation.gov.uk
served. Before hashing, the extractor strips trailing whitespace from each
line and rewrites editorial `key-<hex>` anchors inside tags to `key-a<N>`
placeholders. No raw anchors remain in the 47 files.

For the two revised orders, `source_url` is the undated current-version URL
(for example `http://www.legislation.gov.uk/uksi/2026/164/article/8`). That
URL will serve different text once the order is amended again. The archived
XML (`dct:valid` 2026-06-15) is the record of what was captured.
legislation.gov.uk also serves that point in time under a dated URL ending
`/2026-06-15`.

## Which version of each order

legislation.gov.uk serves revised text only for instruments its editors have
revised. At the default URL on 2026-09-27:

- SI 2023/329, SI 2024/300, SI 2025/228 and SI 2026/555 have no revised
  version. The default `data.xml` redirects to `/made/data.xml`, and each row's
  `source_url` ends in `/made`. For these the made text is the operative text.
- SI 2022/365 and SI 2026/164 are revised. The default URL serves the current
  version, and every archived article file carries `dct:valid` 2026-06-15.
  The instrument-level `data.xml` lists these versions: for SI 2022/365, made,
  2022-03-23, 2023-03-23, 2024-03-23, 2025-03-23, 2026-03-23 and 2026-06-15;
  for SI 2026/164, made, 2026-03-23 and 2026-06-15. Article-level files list
  only the versions in which that article changed. For example, SI 2022/365
  arts 1-3 list made and 2022-03-23, and art. 4 adds 2026-06-15.

The current SI 2026/164 text reflects SI 2026/555 art. 2:

- art. 1(2) reads "ending with 31st December 2026";
- art. 1(3) is omitted (". . ." in the text);
- art. 1(4) reads "beginning with 1st January 2027 and ending with 28th
  February 2027";
- art. 3 reads "continues in force until the end of 31st December 2026";
- arts 4-7 are omitted (their row bodies are only the omission dots).

The current SI 2022/365 text reflects SI 2026/555 art. 3. In art. 4 Table C,
rows (b), (c), (f) and (g) read 9.96 in column (C) and 0.0648 in column (D).

The heading substitution in SI 2026/555 art. 2(5) ("1st January 2027" in the
headings of arts 8-11) is also applied on legislation.gov.uk. The corpus rows
do not carry it, because the extractor gives provisions a structural heading
("Article 8") and does not copy the P1group title. Art. 1(4), which is in the
corpus, states the same period.

## Currency and outstanding effects

- The 1979 Act and order sources list no unapplied effects.
- A verifier checked legislation.gov.uk's effects feeds on 2026-09-27
  (`/changes/affected/uksi/2026/164`, `/changes/affected/uksi/2022/365`,
  `/changes/affecting/uksi/2026/555`). It also searched titles for 2026
  instruments. No instrument other than SI 2022/365, 2023/329, 2024/300,
  2025/228, 2026/164 and 2026/555 affects either order. Every listed effect is
  applied. The newest 2026 UKSI on legislation.gov.uk at the time was
  2026/1053.
- Each ITTOIA 2005 source lists one unapplied effect. It comes from asc/2026/7
  and inserts "s. 168(6)(e) and word", so it touches s. 168, not Part 6A.

The trading allowance text is the form for tax year 2024-25 onwards. Finance
Act 2022 Sch. 1 para. 21 omitted Step 3 (the overlap profit deduction) and
subsection (4) from s. 783AI. Finance Act 2024 Sch. 10 para. 31 substituted
s. 783AE(3). Encoding earlier tax years would need the 2017-11-16
point-in-time versions, as a separate scope.

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

## Verification

Three checks were run over all 47 rows. None of the scripts are committed;
they live in the operator workspace.

1. Against the archived CLML, with a separate parser. The parser walks each
   provision's `P1` in document order and emits each `Text` element as a line
   and each table as its rows. Footnote and commentary text is excluded. The
   result must equal the body exactly, apart from whitespace. That catches
   omissions, reorderings and misplaced table cells. All 47 rows passed. A
   negative control caught a dropped line, a changed cell and two swapped
   lines.
2. Against the legislation.gov.uk HTML page, a separate rendering. Each
   non-table body line and each table cell must be a whitespace-normalized
   substring of the page text. HTML-only apparatus is removed from both sides
   first: `[F<n>` amendment markers, `M<n>` marginal-citation markers, square
   brackets and footnote references. This check shows containment only. It
   cannot detect omissions or a cell in the wrong place; check 1 covers those.
   All 47 rows passed. A negative control rejected "0.5296", "8.64", "ending
   with 31st August 2026" and "beginning with 1st December 2026".
3. Independent verifiers for the first 39 rows, working from fresh fetches.
   They compared all 117 ITTOIA body lines with the section XML, in order.
   They compared every cell of Tables A to E with the live CLML, and
   recomputed column (D) from columns (B) and (C) to 4 decimal places.

## Extractor behaviour an encoder should know

These are properties of the existing UK CLML extractor, not of this run:

- Bodies omit the provision numbers: "(1)", "(a)" and the article number.
- Table captions ("Table A", "Table D") are not carried. Tables are rendered as
  Markdown after the provision's text, in source order. SI 2022/365 art. 3 and
  SI 2026/164 art. 8 each carry two tables: the per-litre table (A or D) first,
  then the road fuel gas table (B or E).
- Footnotes and legislation.gov.uk annotations are not carried. Two cases
  matter here:
  - SI 2022/365 art. 4 has drafting footnotes on Table C. One, on the
    "Percentage addition" column, says the adjusted rebate "is also calculated
    by reference to the underlying rate of duty set by the Oil Act that
    applies to the product, and not by reference to that rate as adjusted by
    article 3". The rule it restates is 1979 Act s. 1(4), which is in the
    corpus.
  - ITTOIA Part 6A Chapter 1 carries an editorial C note: "Pt. 6A Ch. 1
    excluded (22.7.2020) by Finance Act 2020 (c. 14), Sch. 16 para. 4(4)". That
    exclusion covers coronavirus self-employment income support scheme
    payments. Encoding 2020-21 or 2021-22 would need to cite it separately.
- In 1979 Act s. 2(7), the "[" after "which" and the "]" after "amount
  payable," are legislation.gov.uk amendment brackets for the Finance Act 1982
  s. 10(3) substitution. The CLML stores them as literal text, so the body
  keeps them. They are not words of the Act.
- The missing opening quote in SI 2026/555 art. 3(b) (`substitute 0.0648”`) is
  in both the CLML and the HTML. It is kept verbatim.

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
after an 8.63 percentage deduction. The earlier note now points here.

## Citation-path ratchet

The ITTOIA section numbers carry uppercase letters, so the new paths count
toward the `uppercase_segments` family in `scripts/validate_citation_paths.py`.
`uk/statute/ukpga/2005/5/783A` already exists (scope
`2026-06-01-uk-frs-microsim`, a Lex capture). The other 18 paths, 783AA to
783AR, are new unique paths, so the baseline in `schema/citation-path.v1.json`
rises from 16280 to 16298. The validator's live count on this branch is 16298.
The order article paths are lowercase and do not affect any ratchet.

## Landing and next steps

- Push this branch to TheAxiomFoundation/axiom-corpus, not a fork. Update it
  from `main` by merging, never by rebasing. Merge the PR with a merge commit,
  never squash. The signed ingest manifests record the data commit, which must
  stay an ancestor of `main`.
- The encoder can cite these scopes only after three more steps:
  1. Cut and merge a UK release selector that carries them, the next
     `manifests/releases/uk-rulespec-*.json` after `uk-rulespec-2026-09-07`.
     It should not also carry `2026-06-01-uk-frs-microsim`, which has its own
     `.../783A` row.
  2. Publish it. `publish.yml` runs `scripts/publish_corpus.py` when a selector
     lands on `main`. That stages the rows and writes the signed release object
     with its `content_sha256`. Activation for serving is a separate step (see
     `docs/named-release-publication.md`).
  3. Rebind rulespec-uk's `.axiom/toolchain.toml` to the release name and
     `content_sha256`.
