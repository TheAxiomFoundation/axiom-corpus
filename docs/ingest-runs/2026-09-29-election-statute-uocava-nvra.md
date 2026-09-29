# 52 U.S.C. 20302, 20310 and 20507: first Title 52 election statutes (2026-09-29)

Title 52 (Voting and Elections) had no rows in the corpus: no tracked `us/statute` provisions file
carried a `us/statute/52` citation path before this run (the only textual hits were
`metadata.references_to` entries in the 2026-07-13 recovery scope). This run adds one `us/statute`
scope holding three whole sections from the official U.S. Code (Office of the Law Revision Counsel,
uscode.house.gov, USLM XML) so RuleSpec encodings of voter-eligibility and deadline rules can cite
them:

- 52 U.S.C. 20302, State responsibilities under the Uniformed and Overseas Citizens Absentee Voting
  Act (UOCAVA), including (a)(8), the 45-day absentee ballot transmission rule;
- 52 U.S.C. 20310, UOCAVA definitions, including "absent uniformed services voter" (paragraph (1))
  and "overseas voter" (paragraph (5));
- 52 U.S.C. 20507, National Voter Registration Act requirements for the administration of voter
  registration, including (a)(1), the latest registration deadline a State may set by registration
  channel.

It uses the `extract-usc --source-zip` adapter, the path of the 2026-09-13 federal statute layer
(`docs/ingest-runs/2026-09-13-federal-statute-layer.md`) and the 2026-09-23 PolicyBench scopes
(`docs/ingest-runs/2026-09-23-tax-statute-policybench.md`).

| Scope (`us/statute`) | Sections | Rows | Source | Expression date |
| --- | --- | ---: | --- | --- |
| `2026-09-29-election-statute-uocava-nvra-title-52` | 20302, 20310, 20507 (+ Title 52 root) | 162 | release point 119-111 | 2026-09-18 |

Coverage complete (162 source rows = 162 provision rows, 0 missing, 0 extra, 0 duplicate
citations). Every row has a heading or a body. Every inventory item and provision row names the one
retained source file, and every inventory item records that file's SHA-256.

## Source

The OLRC download page (`https://uscode.house.gov/download/download.shtml`, read
2026-09-29T17:18Z) lists the current release point as **Public Law 119-111 (09/18/2026)**. Title 52
is not in bold there, so it has not changed since the prior release point. The XML carries
`docPublicationName Online@119-111`, the note "Current through 119-111", and
`dcterms:created 2026-03-26T12:30:07`.

| Release point | Zip URL | Zip bytes | Zip SHA-256 | Member | Member bytes | Member SHA-256 | Retrieved |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| 119-111 (09/18/2026) | `https://uscode.house.gov/download/releasepoints/us/pl/119/111/xml_usc52@119-111.zip` | 258,618 | `3fd8b179d10463e9651b148c75b1e0ad9294169e56a059b87786a4ea16167e60` | `usc52.xml` | 1,790,311 | `f22fe4dd407b9ce6e6d31c5d17cceb24f5e05da0c73c6225150ef897f2dc201d` | 2026-09-29T17:19:15Z |

The zip is retained byte-for-byte as
`sources/us/statute/2026-09-29-election-statute-uocava-nvra-title-52/olrc/xml_usc52@119-111.zip`, the
scope's only source file. Rows carry `metadata.source_archive_member: usc52.xml`.
`--source-as-of` and `--expression-date` are the release point's date, 2026-09-18, the convention of
the 2026-09-13 and 2026-09-23 scopes; the XML creation date is in every row's
`metadata.created_date`.

### Why OLRC USLM, not the GovInfo section HTML

The GovInfo precedent (`manifests/us-usc-26-85.yaml`, `extract-official-documents` with
`anchor_range`) yields one section row per section. The encodings this run serves cite paragraphs
(`us/statute/52/20302/a/8`, `us/statute/52/20310/1`, `us/statute/52/20310/5`,
`us/statute/52/20507/a/1`), which only a subsection-level extraction can answer. OLRC is the same
official publisher as every held `us/statute` scope, and its release-point XML goes through the same
adapter.

## Title root

No scope carries `us/statute/52`, so this scope takes the title row with `--include-title`, as the
Title 19 spine did (`us/statute/2026-08-03-tariff-title-19-spine-with-root-title-19`). The three
section rows have `parent_citation_path: us/statute/52`, which resolves inside the scope, so no row
needs `scripts/self_contain_usc_scope.py` (running it would detach nothing). The title row's
`metadata.section_count` (171) counts the title's sections in the XML, not the sections selected. A
later Title 52 scope that selects this one in the same release must leave out the title row, or
supersede this scope.

## Rows

| Section | Rows | Subsections | Paragraphs | Subparagraphs | Clauses | Subclauses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20302 | 69 | 9 ((a)-(i)) | 29 | 22 | 8 | 0 |
| 20310 | 17 | 0 | 8 ((1)-(8)) | 8 | 0 | 0 |
| 20507 | 75 | 10 ((a)-(j)) | 26 | 28 | 8 | 2 |

Plus the title row: 162 rows. Rows the encodings need, all present:

- `us/statute/52/20302/a/8` with `a/8/A`, `a/8/B`, `a/8/B/i`, `a/8/B/ii`;
- `us/statute/52/20310/1` with `1/A`-`1/C`, and `us/statute/52/20310/5` with `5/A`-`5/C`;
- `us/statute/52/20507/a/1` with `a/1/A`-`a/1/D`.

Source notes carried as-is:

- `us/statute/52/20507/h` is "Omitted" with an empty body: the source subsection is a heading with
  `<content/>`.
- `us/statute/52/20302/a/9` (and the bodies of `20302/a` and `20302`) include the inline USLM
  footnote "1 So in original. Probably should be 'in a manner'.", which the adapter keeps in the
  body; the OLRC reader page shows it as a footnote.

## Currency check against the OLRC reader

The OLRC preliminary reader pages
(`https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title52-section<n>&num=0&edition=prelim`,
retrieved 2026-09-29T17:43Z) were compared word by word, from the section heading to the source
credit, with the section row's body (em dashes and punctuation spacing normalized, HTML comments
dropped):

| Section | Page SHA-256 | Page words | Row words | Result |
| --- | --- | ---: | ---: | --- |
| 20302 | `34f0c641e19dd8adf992177d75659326d14d4c70ccc5af45451ed87ffb699b9b` | 2,416 | 2,426 | identical except the 10-word "So in original" footnote above |
| 20310 | `ca48d892f2694eb8cc937e138f6d84c7238f1c13e5a0cd12438b2e404c0c4854` | 483 | 483 | identical |
| 20507 | `1906b1d41074004148deb3106e17e7dae4b25b5ab4a2981a8d3c824831062646` | 2,152 | 2,152 | identical |

## Commands

```bash
B=data/corpus
uv run axiom-corpus-ingest extract-usc --base $B --version 2026-09-29-election-statute-uocava-nvra \
  --source-zip xml_usc52@119-111.zip --title 52 --source-as-of 2026-09-18 --expression-date 2026-09-18 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/111/xml_usc52@119-111.zip \
  --section 20302 --section 20310 --section 20507 --include-title

uv run --extra dev axiom-corpus-ingest coverage --base $B \
  --source-inventory $B/inventory/us/statute/2026-09-29-election-statute-uocava-nvra-title-52.json \
  --provisions $B/provisions/us/statute/2026-09-29-election-statute-uocava-nvra-title-52.jsonl \
  --jurisdiction us --document-class statute \
  --version 2026-09-29-election-statute-uocava-nvra-title-52 --write
```

`extract-usc` appends `-title-52` to `--version` (`usc_run_id`) and names the retained source after
the local zip file, so the zip is passed under its publisher filename.

## Collisions

None of the 162 citation paths is carried by any tracked `us/statute` provisions file
(`git grep` over `data/corpus/inventory/us/statute/` and `data/corpus/provisions/us/statute/` on
`origin/main` at `dbb69efb8`; the only hits are `references_to` values in
`2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup`, which has no Title 52 row).

## Citation-path grammar

`scripts/validate_citation_paths.py` failed only on the `uppercase_segments` ratchet: 16,357 live
against a 16,281 baseline. The new scope adds exactly 76 unique uppercase paths, all US Code
subparagraph letters and subclause numerals (for example `us/statute/52/20302/a/8/A`,
`us/statute/52/20507/e/2/A/ii/I`), the category the schema documents. The baseline in
`schema/citation-path.v1.json` is raised to 16,357. No space or en-dash segment is added. Other
branches that raise this ceiling will conflict on that line; recompute it on merge.

## Not done here

- The scope is not in any release selector on this branch. A minimal-delta successor to the
  release `rulespec-us` pins is cut in a separate, stacked pull request, because merging a
  `manifests/releases/*.json` file runs `publish.yml`.
- Nothing is published or activated.
