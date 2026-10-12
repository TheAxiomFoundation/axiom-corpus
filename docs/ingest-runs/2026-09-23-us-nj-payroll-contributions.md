# New Jersey payroll contribution statutes and NJDOL rate page

Date: 2026-09-23
Work order: PolicyBench root cause r05 (New Jersey worker unemployment insurance and workforce
fund contributions missing from payroll tax). The Axiom encodings that would serve as the
oracle for the upstream fix need N.J.S.A. 43:21-7 (in particular (b), with the taxable wage
base in (b)(3), and (d)(1), worker contributions) and the workforce fund sections
N.J.S.A. 34:15D-13 and 34:15D-22.
Branch `ingest-pb-nj-43-21` cut from `origin/main` (942e138e7).

## Before this run

None of the target sections resolved on `main`. The tracked New Jersey statute scopes were
`2026-07-13-recovery` (one row, `us-nj/statute/54a:4-7`) and
`2026-07-16-pit-central-us-nj-title-54a` (Title 54A only, 256 rows). No tracked provision row
had a `us-nj/statute/43:*`, `us-nj/statute/34:*`, `chapter-43:*`, `chapter-34:*`, `title-43` or
`title-34` citation path, and every tracked release selector that carries `us-nj/statute`
carries only those two versions.

## Statute scopes (Titles 43 and 34)

Method. `manifests/us-nj-titles-34-43-payroll-contributions.yaml` runs the existing
source-first `new-jersey-statutes` adapter through `extract-state-statutes` against the
Legislature's official bulk release, `https://pub.njleg.state.nj.us/Statutes/STATUTES-TEXT.zip`,
the same source and adapter as the released Title 54A scope. The adapter filters at title
grain only, so each scope carries the whole enclosing title (a superset of chapters 43:21
and 34:15D). Both sources share one download cache, so both scopes are cut from the same ZIP.

Retrieval. The adapter download cache was written at 2026-09-23T15:55:46Z. A fresh download
of the same URL at 17:03Z with the corpus user agent (`HTTP 200`,
`Last-Modified: Wed, 23 Sep 2026 10:00:44 GMT`, `Content-Length: 41343040`) was byte-identical
to the retained ZIP. The ZIP dates both members (`STATUTES.TXT`, `STATUTES.RTF`)
2026-09-23 06:00, and the text opens "UPDATED THROUGH P.L.2026, c.30, and J.R.1".

| retained file (in each title scope) | bytes | SHA-256 |
|---|---:|---|
| `new-jersey-statutes-text-zip/STATUTES-TEXT.zip` | 41,343,040 | `a92d4282780751f57570ebab87090886e0a39101800f5df200202f77736d3f2b` |
| `new-jersey-statutes-text/STATUTES.TXT` | 84,005,944 | `00187b070cd63669c58ecc1d2e1088cbbe2ab121b367c6acf3876558b29ff466` |

| scope version | title | chapters | sections | rows | complete |
|---|---|---:|---:|---:|---|
| `2026-09-23-payroll-contributions-us-nj-title-43` | 43, Pensions and Retirement and Unemployment Compensation | 35 | 1,405 | 1,441 | yes |
| `2026-09-23-payroll-contributions-us-nj-title-34` | 34, Labor and Workmen's Compensation | 45 | 2,106 | 2,152 | yes |

### Adapter repairs

Three defects in the existing adapter touched these scopes. Each repair is covered by a
regression test in `tests/test_corpus_new_jersey.py`, and the counts below come from parsing
the whole `STATUTES.TXT` (all titles) with the adapter at `main` (942e138e7) and with the
repaired adapter.

**Repeated section headers.** The bulk file sometimes prints one section header over two
separate blocks of text, and the adapter mishandled both shapes:

- A non-adjacent repeat was skipped with its whole body. In Title 34 this dropped
  N.J.S.A. 34:15C-10.5 (P.L.2021, c.27, s.16, the private career school teach-out agreement),
  which the bulk file heads "34:15C-10." after 34:15C-10.4. The official chapter law
  (`https://pub.njleg.state.nj.us/Bills/2020/PL21/27_.HTM`, fetched 2026-09-23, SHA-256
  `1ced75e19a7e307045001a1c795b5b141086e0c9fd4ff03c31565e3ebb20ac2f`) prints the same
  "C.34:15C-10." codification header over section 16, while its section 17 cross-refers to it
  as "section 16 of P.L.2021, c.27 (C.34:15C-10.5)".
- A repeat directly after body text was treated as a repeated self-header, so the first
  block's body was thrown away and replaced by the second. `us-nj/statute/34:16-43` carried the
  heading "Authority of division and commission" over the superseded 1979 text, and the
  current text (history "L.1971, c. 272, s. 5. Amended by L.1979, c. 335; 2017, c.131, s.137.")
  was lost.

The adapter now absorbs a repeated header when no text separates it from the previous one
(the adjacent-duplicate case, such as `43:17-9`), and folds a header that the publisher
reprints partway through one section back into that section: same heading, and the text so
far has no source-history line yet. The only such case in the bulk text is 52:27D-18.5, reprinted
between subsections c. and d. It used to lose subsections 2. through c. and is now one section.
Every other later block becomes its own section under the repository's same-number variant
convention (`<section>--variant-N`, `citation_segment.variant_segment`, as in the Delaware,
Nevada, New Mexico and Rhode Island adapters). Each such row carries `metadata.variant`,
`metadata.canonical_citation_path` (the plain section path) and a `new_jersey:variant`
identifier. The first block lists its variants in `metadata.variant_citation_paths`. Over the
whole bulk text this keeps 21 variant rows (15 in Title 18A, 2 in Title 34, and 1 each in Titles
12A, 45, 48 and 52), restores the first block's own body for 34:16-43, 45:15-16.52 and
52:17B-194.20, and makes 52:27D-18.5 whole. No section heading changes. Title 54A and Title 43
have no repeated headers. In this run's Title 34 scope the repair adds
`us-nj/statute/34:15c-10--variant-2` and `us-nj/statute/34:16-43--variant-2`, restores the
current body of `34:16-43`, and shifts the ordinals of later Title 34 sections by one or two.

**Title boundaries.** A section body ran to the next section header and ignored TITLE and
APPENDIX header lines, so the last section of each title ended with the next title's header
(in this run, `43:23-33` ended "TITLE 44 POOR" and `34:21-20` ended "TITLE 35 LEGAL
ADVERTISEMENTS"). Sections now end at the next TITLE/APPENDIX line. Over the whole bulk text this
removes a trailing title header from 68 section bodies. Two of them were longer: `7:5-12` carried
both "TITLE 8A CEMETERIES" (a title with no sections) and "TITLE 9 ...", and `59:14-4` carried the
Appendix A revision note. The one text printed between a title header and its first section,
that Appendix A revision note, is now the body of `us-nj/statute/title-app-a`.

**Status metadata.** `metadata.status` was set to `repealed`, `expired` or `omitted` whenever the
word appeared anywhere in the heading or body. That marked live law as dead: "shall not be
decreased, increased, revoked or repealed", "whose term shall have then expired", "(fractional
part of a dollar omitted)", and repealer sections, which are themselves in force. Status now comes
only from a heading that is itself a status note ("Repealed", "Repealed by L.2005,c.83,s.20, ...")
or from the final clause of the section's last source-history paragraph ("...; repealed R.S.
46:38A-57 (effective July 1, 2007).", "...; per s.4, expired April 19, 1993."). "Repealed in part"
does not count. Over the whole bulk text the flags go from 574 repealed, 388 expired and 122
omitted to 31 repealed and 184 expired. Each of the 31 has a "Repealed" heading or a final
history clause recording the repeal, and each of the 184 ends its history with a statutory
expiration note. In this run's scopes, Title 43 keeps only `43:21-14a` and `43:21-14b` (both
"per s.4, expired April 19, 1993."), losing 31 repealed, 7 expired and 2 omitted flags. Title 34
loses all 12 repealed, 9 expired and 3 omitted flags. None of the target sections carries a
status.

### Checks beyond the adapter's own coverage report

The adapter's coverage report compares the inventory and provisions written from one parse,
so it cannot see text the parse never assigned or text assigned to the wrong row. These
independent checks read `STATUTES.TXT` directly:

- Section set. The distinct flush-left section headers for each title match the parsed
  section labels exactly (1,405 for Title 43, 2,104 distinct labels for Title 34, whose two
  repeated labels give the 2,106 section rows).
- Text conservation, both directions. Each provision's raw block runs from its header line to
  the next header of a different provision or the next TITLE/APPENDIX line, whichever comes
  first. Comparing whitespace-separated tokens for every section:
  - Body to raw block: no provision body in either title holds a token absent from its own
    raw block. Before the title-boundary repair, `43:23-33` and `34:21-20` did.
  - Raw block to body: every token appears in the provision's body, except the
    citation-and-heading text the adapter deliberately strips when a body's first line repeats
    its own header (8 tokens in 3 Title 43 sections, 29 tokens in 5 Title 34 sections). Before
    the repeated-header repair, a title-wide token count found 346 Title 34 tokens missing from
    the provision bodies.
  - The three target sections match their raw blocks exactly in both directions.
- No section row has an empty body, every parent path is in its scope, no citation path
  repeats, no section body contains a TITLE or APPENDIX paragraph, and every row carries
  `source_as_of` and `expression_date` 2026-09-23.

Target sections:

- `us-nj/statute/43:21-7` ("Contributions", 76,504 characters) holds subsections (a) through
  (e), including (b)(3), the promulgated taxable wage base (28 times the Statewide average
  weekly remuneration, not less than the FUTA wage base), and in (d)(1)(D) the worker
  contribution from January 1, 2024 of 0.3625% of wages to the unemployment compensation fund
  and 0.0200% to the unemployment compensation administration fund. Its source history ends
  "2024, c.101; 2024, c.102, s.5."
- `us-nj/statute/34:15d-13` ("Employer and worker contributions"): worker 0.025% of wages
  (as determined under 43:21-7(b)(3)) to the Workforce Development Partnership Fund from
  January 1, 1993.
- `us-nj/statute/34:15d-22` ("Contributions to fund"): worker 0.0175% of those wages to the
  Supplemental Workforce Fund for Basic Skills from January 1, 2002.

Section grain only. The adapter emits one row per section, so (b)(3) and (d)(1) are addressed
inside the `43:21-7` body. `generate-anchors --target us-nj/statute/43:21-7` rejects the
section ("duplicate anchor citation paths (ambiguous paragraph parse)"), and the two 34:15D
sections yield no paragraph anchors, so no anchors layer was added.

Known gap: N.J.S.A. 34:15C-10.5. The row `us-nj/statute/34:15c-10--variant-2` holds the text the
chapter law codifies as 34:15C-10.5 (see the repeated-header repair above). The corpus keeps the
publisher's printed header as the path, so that row's `canonical_citation_path` is
`us-nj/statute/34:15c-10`, and `34:15c-10.6` lists `us-nj/statute/34:15c-10.5` in
`metadata.references_to`, a path no row carries. Resolving it needs a policy for correcting
publisher misprints (for example a `codified_as` field sourced to P.L.2021, c.27, s.17); this
run does not set one. The section is not a PolicyBench target.

## Guidance scope (NJDOL rate page)

`manifests/us-nj-njdol-contribution-rates.yaml` snapshots the NJDOL Division of Employer
Accounts page `https://www.nj.gov/labor/ea/employer-services/rate-info/` through
`extract-official-documents` as `us-nj/guidance/2026-09-23-njdol-contribution-rates`
(retained file written 2026-09-23T15:55:59Z; 137,432 bytes; SHA-256
`c83bf85d56629e40456c2ab45c88e55a9f70eb91804a97ee026c73d851b913a7`). A fresh fetch at 17:14Z
with the corpus user agent was byte-identical. A later fetch at 18:02Z returned 137,566 bytes
whose only difference is an appended Incapsula bot-management `<script>` tag, so a re-fetch
can differ in bytes without any change to the page text. The page's year labels sit inside accordion
`<button>` toggles, which the HTML extractor always drops, so the manifest uses `anchor_range`
segmentation with one explicit range per accordion card: six information cards (overview, how
rates are calculated, base weeks, quarterly due dates, the fiscal year 2026-27 rate notice,
voluntary contributions) and one card per calendar year 2027 back to 2015, at
`us-nj/guidance/njdol/employer-services/rate-info/<label>`. The toggle labels read 2027 down to
2015 in document order, matching the `nth-of-type` ranges, and each year block's text names its
own year far more often than any other. Of the content column's 4,215 tokens (toggles
removed), the only ones absent from the provision bodies are the six words of the page title,
which is the overview row's heading. The 2026 block reads worker U.I. 0.003825, D.I. 0.0019,
W.F./S.W.F. 0.000425, F.L.I. 0.0023 (January 1 to December 31, 2026) and a 2026 UI and WF/SWF
taxable wage base of $44,800; the worker U.I. and W.F./S.W.F. rates equal the sums of the
statutory rates above (0.3625% + 0.0200%; 0.025% + 0.0175%). 20 rows (document root plus 19
sections), coverage complete.

## Reproduction

- Statutes: `extract-state-statutes` on a scratch copy of the manifest whose only difference is
  a `download_dir` holding the 17:03Z download rewrote sources, inventory, provisions and
  coverage identical to the pre-repair artifacts. After all three repairs,
  `extract-state-statutes --base data/corpus --manifest
  manifests/us-nj-titles-34-43-payroll-contributions.yaml` (from the retained download cache)
  rewrote both scopes with byte-identical sources and the same row counts. The Title 43 rows
  differ from the pre-repair extraction only in the `43:23-33` body and 40 status flags. The
  Title 34 rows differ only in the `34:21-20` body, 24 status flags and the two variant rows
  and links.
- Guidance: `extract-official-documents --manifest manifests/us-nj-njdol-contribution-rates.yaml`
  into a scratch base, fetching live at 17:15Z, rewrote identical source, inventory,
  provisions and coverage.
- `axiom-corpus-ingest coverage --write` left all three coverage files unchanged.

## Release selection

A named release that should carry these records selects:

```json
{"jurisdiction": "us-nj", "document_class": "statute", "version": "2026-09-23-payroll-contributions-us-nj-title-43"}
{"jurisdiction": "us-nj", "document_class": "statute", "version": "2026-09-23-payroll-contributions-us-nj-title-34"}
{"jurisdiction": "us-nj", "document_class": "guidance", "version": "2026-09-23-njdol-contribution-rates"}
```

Activation repoints each `(jurisdiction, document_class)` pair to the activated release and
serves every version that release carries for the pair
(`supabase/migrations/20260718193000_scope_level_activation.sql`), so the new release must
also keep the us-nj statute and guidance scopes it should go on serving. In
`us-rulespec-2026-09-14-wave4-r2-union` those are statute `2026-07-13-recovery` and
`2026-07-16-pit-central-us-nj-title-54a`, and guidance `2026-09-14-msp-income-standards` and
`2026-09-14-snap-fy2026-state-transmittal`. On the final artifacts, none of the 3,613 new
citation paths collides with the 3,658 `us-nj` paths of that selector, and two local, untracked
draft selectors passed `validate-release --strict-warnings` with 0 issues: the three new scopes
alone, and that selector's 18 us-nj scopes plus the three new ones (21 scopes).

## Not done here

- Ingest manifests. No `.axiom/ingest-manifests/us-nj/...` file exists yet for the three
  scopes. `sign-ingest-manifest` needs `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and records
  `axiom_corpus_git.dirty_tracked`, which must be false, so signing follows the commit of these
  artifacts, as the Canada surtax orders ingest did (`87928f0d1`, then `36e82410e`). CI's
  `guard-ingested` fails until the signed manifests are committed.
- The released `2026-07-16-pit-central-us-nj-title-54a` scope is not re-emitted. Released
  versions are immutable, so it still carries the two defects the repairs fix. `54a:12-6` ends
  with "TITLE 55 TENEMENT HOUSES AND PUBLIC HOUSING", and five live sections carry a false
  status (`54a:2-1.2` and `54a:9-24` repealed, `54a:9-9` and `54a:9-14` expired, `54a:9-4`
  omitted). Re-parsing its retained source with the repaired adapter differs from the released
  rows in exactly those six rows, so a re-extraction under a new version would clear them. The
  re-parse also emits `54a:4-7`, which the adapter at `main` emits as well and which the
  released selectors carry in the `2026-07-13-recovery` scope instead.
- Nothing was published to R2, loaded to Supabase, or added to a tracked release selector.
