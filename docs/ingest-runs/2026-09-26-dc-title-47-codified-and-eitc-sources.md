# D.C. Code title 47 from law-xml-codified, plus DC EITC sources for TY2022-TY2023

Date: 2026-09-26. Branch `ingest/dc-title-47-current-2026-09-26`, cut from
`origin/main` f1916d73b. Purpose: step 1 of TheAxiomFoundation/rulespec-us#1420
(DC EITC, D.C. Code § 47-1806.04(f)). The pinned DC title 47 text was about ten
years out of date, and the TY2022/TY2023 amounts the encoding needs were not in
the corpus.

Three new scopes:

| Scope | Rows | Source |
|---|---|---|
| `us-dc/statute/2026-09-26-codified-title-47` | 2,179 | DCCouncil/law-xml-codified `publication/2026-05-23` @ `3a3c8eaf780a` (2026-09-16) |
| `us-dc/form/2026-09-26-dc-otr-d-40-booklets-ty2022-ty2023` | 182 | OTR 2022 and 2023 D-40 booklets (January revisions) |
| `us/guidance/2026-09-26-irs-rev-procs-2021-45-2022-38` | 59 | Rev. Proc. 2021-45 and Rev. Proc. 2022-38 |

No R2 upload, Supabase load, publication or activation was run for this ingest.

## Why `2026-07-16-pit-east-title-47` was stale

- `manifests/state-income-tax-recovery.yaml` (entry `us-dc-code`) extracted it
  from a copy of `sources/dc/dc-law-xml/us/dc/council/code/titles`, the local
  clone that `manifests/state-statutes.current.yaml` named.
- That clone is DCCouncil/dc-law-xml. Its `us/dc/council/code/titles` tree is not
  the maintained Code. All 1,826 section files in the pit-east source directory
  are byte-identical (git blob hash) to that tree at dc-law-xml main `a685aaa`
  (2026-09-23). For example, 47-1806.04.xml is blob `cc41d7fc2a`, and its only
  upstream commit is `db034d7fb013` (2021-10-17, message "2019-01-04").
- The newest history note in those title 47 files is D.C. Law 21-98 (D.C. Act
  21-307), both from Council Period 21. The title 4 files stop at D.C. Law 22-65.
- `source_as_of` and `expression_date` were hardcoded to `2025-12-23` in
  `manifests/state-statutes.current.yaml` (added in 19c99dc01, 2026-05-01) and
  copied into the recovery manifest. The date is therefore not the date of the
  text.
- The maintained codified XML, the XML that code.dccouncil.gov serves, is
  DCCouncil/law-xml-codified.

## Which law-xml-codified branch is current

- The repository's default branch, `publication/2021-10-18`, stopped on
  2026-05-19 (`6231fae`).
- On 2026-05-23 the Council re-rooted the history as `publication/2026-05-23`,
  which has no common ancestor with the default branch. It carries 389 commits
  and runs through `3a3c8ea` "2026-09-16/2026-09-16", which equals
  `publication/2026-05-23.2026-09-16`.
- Between the two heads, 501 title 47 files differ, 236 of them beyond the new
  `target-path` annotation attributes.
- The live site serves the newer lineage. For example, § 47-1803.02(a)(2)(BBB)
  (the § 42-2083 loan-forgiveness exclusion, committed 2026-08-26) is on
  https://code.dccouncil.gov/us/dc/council/code/sections/47-1803.02 on
  2026-09-26 and is absent from the default branch.
- For § 47-1806.04, the two heads differ only in annotation attributes.
  `sections/47-1806.04.xml` at the default branch is the file
  rulespec-us#1420 cites (sha256 `69c54aa7…8fbb`, blob `02abb9e2`). At
  `3a3c8ea` it is blob `ba415dfa`, with the same text.

The checkout used: a blobless clone of law-xml-codified at
`~/.axiom/sources/dc/law-xml-codified`, sparse to `titles/4` and `titles/47`,
detached at `3a3c8eaf780a8e6e4bb266550671da91320404bd`, clean.

## Extractor fix: `<aftertext>`

`_dc_para_text` read only `<num>`, `<heading>`, `<text>` and child `<para>`
elements, so `<aftertext>` was dropped. That element is text that closes a
paragraph after its subparagraphs. In title 47 this lost:
- the operative proviso of § 47-1002(20) ("As the exemption provided for in
  subparagraph (A)(vi) ... applies to the Southern Court project ... it shall be
  effective ...");
- four article subheadings of the Multistate Tax Compact in § 47-441.

`_dc_aftertext_lines` now emits the element at its paragraph's indent, in
document order (`src/axiom_corpus/corpus/states.py`). Body indentation mirrors
the upstream XML nesting, not the legal structure. For example, the § 47-1002
proviso sits inside `(D)` in the XML, although it refers to paragraph (20).
Similarly, § 47-1806.04(e)(2)(C) is nested as a sibling of (2) upstream. A new test,
`test_dc_section_body_keeps_aftertext_at_paragraph_level`, pins the output.

## D.C. Code title 47

Command:

```bash
uv run axiom-corpus-ingest extract-dc-code --base data/corpus \
  --version 2026-09-26-codified \
  --source-dir ~/.axiom/sources/dc/law-xml-codified/us/dc/council/code/titles \
  --only-title 47 --source-as-of 2026-09-16 --expression-date 2026-09-16
```

- Output: 1 title, 63 chapters, 103 subchapters, 38 parts, 1,975 sections, so
  2,180 rows. Coverage is complete.
- `source_as_of` and `expression_date` are 2026-09-16, the committer date of
  `3a3c8ea`. The text is the Code as published that day, including temporary
  legislation then in force (see below).
- Compared with `2026-07-16-pit-east-title-47`:
  - every one of its 2,019 citation paths is still present, with the same row id
    (ids are `uuid5("axiom:" + citation_path)`);
  - 160 paths are new, for example §§ 47-1005.03, 47-1098, 47-1099 through
    47-1099.17, 47-1806.17, and chapters 50 and 51;
  - 341 bodies and 30 headings changed, 32 of the bodies in chapter 18.
- § 47-1806.04 now has (f)(1)(B-1), (B-2), (B-3) and (D).
  - (f)(3)(A) reads "shall be refundable to the individual claiming the credit".
  - (e)(4) reads "For taxable years beginning after December 31, 2017".
- Tables (axiom-corpus#167): 18 tables in six title 47 files (47-1806.03,
  47-1806.06, 47-2711, 47-2712, 47-2718, 47-895.01). Every multi-cell row
  reaches the body as a `cell | cell` line.

**Cross-scope dedup.** `us-dc/statute/47/47-1806.03` is also emitted by
`us-dc/statute/2026-07-13-recovery`. That scope stays in the rulespec releases
because it owns `47-1806.03/block-1`, which 16 excerpts in rulespec-us DC
policy modules cite. As `fbc9f07da` did for pit-east,
`scripts/deduplicate_release_selector.py --apply` removed the section row and its
inventory item from the new scope, so it has 2,179 rows. The removal was checked
against a canonical selector of the draft release's retained scopes. It found
exactly one collision. The source XML stays attested in the scope. The recovery
block's text, fetched from code.dccouncil.gov on 2026-07-14, equals the
`3a3c8ea` section body after whitespace normalization (7,410 characters), so
nothing is lost.

### Temporary and emergency legislation

22 rows start with the Council's `*NOTE: This section includes amendments by
(or was created by) emergency/temporary legislation that will expire on <date>
...*` line. For these sections the permanent text is a separate file,
`titles/99/<section>(Perm).xml`, which the extractor does not read.

| Expires | Sections |
|---|---|
| 2026-09-25 (amended) | 47-1801.04, 47-1803.02, 47-1803.03, 47-1805.02, 47-1806.01, 47-1806.02, 47-1806.04, 47-1806.17, 47-1809.05, 47-1811.04, 47-1812.08 |
| 2026-09-25 (created) | 47-1099.15, 47-1803.04 |
| 2026-11-08 | 47-2851.04, 47-2851.07, 47-2851.10, 47-2853.42, 47-2853.49 (amended); 47-2851.25 (created) |
| 2027-01-01 | 47-813 |
| 2027-01-22 | 47-1099.16 (created) |
| 2027-03-27 | 47-4683 |

The rows are correct for their `expression_date` of 2026-09-16. Encoders reading
them for later dates must check whether the temporary text lapsed or was made
permanent. One example: in § 47-1806.04 the temporary text has (f)(1)(B-2) at
100% from TY2025 and (B-3) repealed. The permanent version has (B-2) at 85% from
TY2025 and (B-3) at 100% from TY2029. (B-1), 70% for TY2022-TY2024, and (D) are
the same in both.

### Checks

- `extract-dc-code` coverage: complete, 0 missing, 0 extra.
- Invariants over all 1,975 section XMLs against their rows:
  - unique citation paths and ids;
  - every `parent_citation_path` present;
  - `expression_date` and `source_as_of` on every row;
  - every word of every `<text>`/`<aftertext>` outside annotations and
    `codify:insert` instructions, and of every paragraph `<num>`/`<heading>`,
    appears in the row body.

  The check reports 0 violations. Run on the pre-fix extraction, it flags
  exactly 47-1002 (63 words) and 47-441 (8 words).
- rulespec-us excerpt check (`origin/main` 54d90a725): every excerpt that cites
  `us-dc/statute/47/*` still matches except three, all in the waived module
  `us-dc/policies/income_tax/2026_resident_liability_source_hold.yaml`:
  - line 313, § 47-1801.04: "Subject to availability of funding";
  - line 318, § 47-1806.02: "increased annually by the cost-of-living adjustment";
  - line 448, § 47-1806.04: "... refundable to the resident claiming the credit".

## IRS Rev. Procs. 2021-45 and 2022-38

Manifest `manifests/us-irs-guidance-ty2022-ty2023-inflation-adjustments.yaml`,
default per-page PDF extraction:

```bash
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-26-irs-rev-procs-2021-45-2022-38 \
  --manifest manifests/us-irs-guidance-ty2022-ty2023-inflation-adjustments.yaml
```

- Rev. Proc. 2021-45: https://www.irs.gov/pub/irs-drop/rp-21-45.pdf, sha256
  `405535647b6287103f5392258d4342cdb70535bf07ff05d89eebc71768083627`.
  - IRB 2021-48 (2021-11-29); `expression_date` 2022-01-01.
  - 29 page rows. The § 3.06 heading is on `page-9`, and the § 3.06(1) table
    ($10,980, $3,733, $20,130, $43,492, $7,320, $560, $9,160, $16,480) is on
    `page-10`.
- Rev. Proc. 2022-38: https://www.irs.gov/pub/irs-drop/rp-22-38.pdf, sha256
  `6c20f8a6c9a3bdf4251fcf50dbf2e2382abc8cbeb1e5e2d3eecdc38b2cbf6bbf`.
  - IRB 2022-45 (2022-11-07); `expression_date` 2023-01-01.
  - 28 page rows. The table ($11,750, $3,995, $21,560, $46,560, $7,840, $600,
    $9,800, $17,640) is on `page-10`.

Both downloads equal the reference copies in
`_axiom-runs/dc-eitc-47-1806-04f-2026-09-26/sources/`.

## OTR D-40 booklets, TY2022 and TY2023

Manifest `manifests/us-dc-individual-income-tax-forms-ty2022-ty2023.yaml`,
`page_citation_prefix: page`, so `page-N` is the PDF page:

```bash
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-26-dc-otr-d-40-booklets-ty2022-ty2023 \
  --manifest manifests/us-dc-individual-income-tax-forms-ty2022-ty2023.yaml
```

- **Dates.** `expression_date` is the first day of the tax year.
  `source_as_of` is the retrieval date, following the TY2025 booklet
  (`manifests/us-dc-individual-income-tax-forms-ty2025.yaml`). The publisher's
  `Last-Modified` dates are in `metadata.publisher_last_modified`. The Rev. Procs.
  instead use the IRB issue date, following
  `manifests/us-irs-guidance-2026-inflation-adjustments.yaml`.
- **Which revisions.** The OTR node pages (`/node/1639856`, `/node/1702786`) now
  link later revisions (March 2023 and April 2024). The manifest ingests the
  January revisions. They match the reference checksums, and OTR still serves
  them at the attachment URLs recorded as `source_url`. The later revision URLs
  are kept in `metadata.later_revision_url`.
- **TY2022.** `2022_D-40_Booklet_Final_blk_01_23_23_Ordc.pdf`, sha256
  `166d3194fa31b293b4fe52ac021406d79b62a5e4fb5d9b6de57773ad980ade85`.
  - Native text layer; 90 page rows (pages 36, 40, 50, 52, 66 and 76 are blank).
  - "Qualifying Child for EITC Purposes" and "permanently and totally disabled"
    are on `page-11`.
  - The no-child worksheet is on `page-23`: $7,320, 0.0765, $560, $20,532,
    0.0848, $27,136.
- **TY2023.** `2023_D40_Book_Final_012324.pdf`, sha256
  `ce1b73c36fd7f263128c72720f0c3c794d9d2d757357469ec29c3da50e386e6c`.
  - The text layer uses Identity-H CID fonts with no ToUnicode map, so native
    extraction yields glyph ids.
  - Extracted with `force_ocr: true`, `ocr_dpi: 300`: tesseract 5.5.3,
    `eng.traineddata` sha256 `7d4322bd…70b2`, about 2.5 minutes. Page-body
    hashes depend on that OCR build.
  - The qualifying-child text is on `page-10`.
  - The worksheet is on `page-23`: $600, 0.0765, $21,888, 0.0848, $28,963.
  - Its earned-income cap prints as **$7,843** ($600 / 0.0765), not the federal
    $7,840. I confirmed this from a 600 dpi render of the page, so it is not an
    OCR error.
  - Leader dots OCR as runs of "c"/"e", and "Line 27e" as "LING 276". Those are
    cosmetic.

## Citation-path ratchet

The two PDF scopes add 237 unique `page-N` paths (57 Rev. Proc. pages plus 180
booklet pages). `schema/citation-path.v1.json` `page_n` was raised from 150,654
to 150,891 with `scripts/validate_citation_paths.py --update-baselines`. Per-page
rows match the Rev. Proc. 2025-32 precedent, where rulespec-us pins page-body
hashes. No other family moved.

## Manifests fixed at the root

- `manifests/state-statutes.current.yaml`: `us-dc-code` now reads a
  law-xml-codified checkout. Its dates are 2026-09-16, and its metadata records
  the repository, branch and commit.
- `manifests/state-income-tax-recovery.yaml`: a comment marks the historical
  `us-dc-code` entry as sourced from the legacy tree and superseded. Its fields
  are unchanged because they record what ran.
- `docs/DC_IMPORT_GUIDE.md` names law-xml-codified and explains how to choose
  the current publication branch. It also documents the temporary/permanent
  split.

## Not done here

- **Title 4.** `us-dc/statute/2026-05-19-title-4` has the same stale source
  (history ends at D.C. Law 22-65; current text runs through 26-55). A
  law-xml-codified extraction gives 878 rows, keeps every old path and id, and
  changes 137 bodies; the § 4-205.52 payment table is intact. It is left for a
  follow-up because the current § 4-205.52 no longer contains three excerpts that
  the unwaived rulespec-us module `us-dc/statutes/4/4-205/52.yaml` quotes (the
  FY 2014/FY 2015 reduction schedule). The TANF module needs re-encoding in the
  same wave as that refresh.
- **Permanent versions.** `titles/99/*(Perm).xml` rows need a citation design
  (compare the California concurrent-version work).
- **History annotations.** `<annotation>` elements (History, Effect of
  Amendments, emergency notes) are still not carried into row metadata; only
  `<annotations>/<text>` is.
