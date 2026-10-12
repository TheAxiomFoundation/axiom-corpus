# Social Security (OASDI): 20 CFR part 404 and SSA POMS RS/GN for the source-conflict register

Date: 2026-10-12 (extraction 15:32 to 15:39 UTC)
Branch: `ingest/ssa-oasdi-source-conflict-texts`, cut from `origin/main` (dd0c062ed).
Impact analysis: no existing function was modified (this worktree is not in the GitNexus index). The one new script,
`scripts/build_oasdi_poms_manifests.py`, loads `scripts/build_ssi_poms_si_manifests.py`
unchanged and calls its `read_index`, `build_documents` and `index_markdown`.

## Why

`TheAxiomFoundation/rulespec-us` `known-source-conflicts.yaml` (rulespec-us#1710) registers
places where the Social Security Act, 20 CFR and SSA's Program Operations Manual System
(POMS) disagree. An entry cites corpus text (`texts`, checked verbatim against the corpus
release rulespec-us pins) or, where the corpus lacks the source, a hash-pinned snapshot
(`pending_texts`). On 2026-10-12, 24 `pending_texts` excerpts in nine entries cited
20 CFR 404.409, 404.412, 404.420 and 404.435 and POMS RS 02501.030, .080, .140,
RS 00615.003, .201, .482, .491, RS 00630.400, RS 00209.001, .015 and GN 02603.045, .050.
None of those was in any corpus scope: no locked `us` provisions file (all 316 checked)
holds a `us/regulation/20/404`, `us/manual/ssa/poms/rs` or `us/manual/ssa/poms/gn` path,
and no manifest on `main` names part 404 or a POMS RS or GN page. This run ingests them so
the register's entries can cite corpus paths once a pinned release carries these scopes.

## Scopes

| jurisdiction | class | version | units | rows | chars | sources | coverage |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| us | regulation | `2026-10-12-title-20-part-404` | 788 sections | 810 | 1,726,565 | 2 files, 7.5 MB | complete, 810/810 |
| us | manual | `2026-10-12-oasdi-poms-rs` | 458 sections | 2,981 | 1,595,805 | 458 files, 19.2 MB | complete, 2,981/2,981 |
| us | manual | `2026-10-12-oasdi-poms-gn` | 12 sections | 73 | 40,103 | 12 files, 0.4 MB | complete, 73/73 |

Every scope: coverage `complete: true`, 0 missing, 0 extra. The 3,864 new citation paths
all match the grammar (`scripts/validate_citation_paths.py`, jurisdiction and document
class consistent, no identity drift) and none is a path of any other locked scope.

## 20 CFR part 404 (eCFR)

```bash
axiom-corpus-ingest inventory-ecfr --base data/corpus --version 2026-10-12 \
  --as-of 2026-10-08 --only-title 20 --only-part 404
axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-10-12 \
  --as-of 2026-10-08 --expression-date 2026-10-08 --only-title 20 --only-part 404
```

- Publisher: eCFR Versioner API only, the path of the released part 416 scope
  (`docs/ingest-runs/2026-09-11-federal-cfr-followon-parts.md`). `titles.json` on
  2026-10-12: title 20 `latest_amended_on` 2026-09-30, `up_to_date_as_of` 2026-10-08, so the
  run uses `--as-of 2026-10-08 --expression-date 2026-10-08` (the 1302 and 416 convention:
  the served point in time, not the run date). The tool names the scope
  `<version>-title-20-part-404`.
- Structure (2026-10-08): 1 part, 22 subparts of which L is reserved, 796 section nodes of
  which 8 are reserved (404.380-404.384 as one node, 404.965, 404.966, 404.1060, 404.1508,
  404.1528, 404.2106, 404.2118), 108 subject groups, 11 appendices. Rows: the part, 21
  subparts and 788 sections (810). The 22 container rows have empty bodies, as in the part
  416 scope; every section body is non-empty (99 to 49,507 characters).
- Appendices not taken. All 11 are subpart-scoped (Appendix to Subpart B; Appendixes, and
  Appendices I to VII, to Subpart C; Appendices 1 and 2 to Subpart P), and
  `--include-appendices` accepts only part-scoped `Appendix X to Part N` identifiers, the
  limit the part 416 run recorded. No register entry cites one. Subpart C's appendices (AWI
  series, benefit formulas, the old-law benefit table, special minimum PIA) are a
  follow-up, by the same route PR #718 used for the part 416 subpart K appendix
  (an official document from the eCFR renderer API) or an adapter change.
- Text kept: `ecfr._section_body` skips `HEAD` and `CITA` (the bracketed Federal Register
  amendment history), and the OMB approval notes (`APPRO`) are not emitted. A word count
  against the XML finds no other missing text (single-token differences such as `i.e. ,`
  against `i.e.,` aside). No section holds an image or `MATH` element; the 3 `img` tags in
  the file are in appendices.
- Tables render one row per line with cells joined by ` | ` (the adapter's `_table_text`),
  e.g. 404.409(b): `Before 1/2/1912 | 62 years.`
- Sources (`sources/us/regulation/2026-10-12-title-20-part-404/ecfr/`):
  `title-20-part-404.xml` 3,528,997 bytes sha256
  `bdf2ce217abc258f999d54f6df1e2c7f6fa7d22ff10b8d0a3b3fc5b086b2fc50` from
  `full/2026-10-08/title-20.xml?part=404`; `title-20.structure.json` 3,980,577 bytes sha256
  `912fc4243129815b9a1d639fcde6885163a8c43f1d7ae8ce5d186e0e41f5d6cc`.
- Timing: `inventory-ecfr` 10 s, `extract-ecfr` 12 s.

## SSA POMS parts RS and GN

```bash
uv run python scripts/build_oasdi_poms_manifests.py --family oasdi-rs --print-index
uv run python scripts/build_oasdi_poms_manifests.py --family oasdi-gn --print-index
axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-10-12-oasdi-poms-rs --manifest manifests/us-ssa-poms-rs-2026-10-12.yaml \
  --source-as-of 2026-10-12 --expression-date 2026-10-12
axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-10-12-oasdi-poms-gn --manifest manifests/us-ssa-poms-gn-2026-10-12.yaml \
  --source-as-of 2026-10-12 --expression-date 2026-10-12
```

- Source: SSA POMS, https://secure.ssa.gov/poms.nsf/. Part RS is chapter-list category 03,
  part GN category 02; the subchapter lists enumerate every section with its `lnx` URL.
  The generator's plain `requests` client got HTTP 200 for every chapter list, subchapter
  list and section page (TLS verified). The manifests keep `request: browser_impersonation:
  true` like the SI and HI manifests; `documents._download_document` makes a plain request
  first and impersonates a browser only when the response needs the fallback. No mirror or
  third-party copy was used.
- Manifests: `scripts/build_oasdi_poms_manifests.py` adds parts RS and GN to the SI/HI
  generator's `PARTS` table at load time and defines two families. It leaves
  `scripts/build_ssi_poms_si_manifests.py` untouched. After PR #718 changed that file, the two manifests regenerate byte-identical from the page cache. It
  fails closed if a selected chapter or subchapter is missing from SSA's index, or if the
  number of sections taken differs from the number the index lists for the selection.
  There is no OASDI agent queue, so it writes only the manifests.
- Same conventions as the SI and HI scopes: one document per section, citation path
  `us/manual/ssa/poms/<part>/<section number>` (regional sections keep their lowercased
  region prefix, e.g. `us/manual/ssa/poms/rs/den00205.250`), one block row per heading
  that carries text (`.../block-N`), extraction `html_content_selector: div.poms` with
  `html_drop_selectors: [p.tninfo, div.poms-citation]`, the transmittal line in
  `metadata.transmittal`, and `expression_date` the section's printed "Effective Dates"
  start date (all 470 sections print one). `metadata.program` is `OASDI`.

### Selection

Every POMS chapter (RS) or subchapter (GN) that holds a section the register cites, or a
section the register's Track B snapshots pin (RS 00605.900 and .910, RS 02505, RS 02510,
GN 02603.010 to .100), taken whole: chapters RS 002, RS 006 and RS 025, and subchapter
GN 02603. Every section the subchapter lists enumerate for a taken subchapter is taken,
including regional sections (8: DAL 4, DEN 2, PHI 1, SEA 1) and the `.000`
table-of-contents sections.

| Chapter / subchapter | Title | Sections listed | Taken |
| --- | --- | ---: | --- |
| **RS 002** | Benefits and Payments | 158 | 158 |
| RS 00200 | Benefits and Payments | 1 | yes |
| RS 00201 | Retirement Insurance Benefits | 4 | yes |
| RS 00202 | Spouse's Benefits | 22 | yes |
| RS 00203 | Child's Benefits | 16 | yes |
| RS 00204 | Lawful Presence Payment Provisions | 18 | yes |
| RS 00205 | Student Benefits | 36 | yes |
| RS 00207 | Widow(er)'s Benefits | 17 | yes |
| RS 00208 | Mother's and Father's Benefits | 26 | yes |
| RS 00209 | Parent's Benefits | 7 | yes |
| RS 00210 | Lump Sum Death Payments (LSDP) | 11 | yes |
| **RS 006** | Determination of PIAs and Benefit Amounts | 222 | 222 |
| RS 00600 | Determination of PIAs and Benefit Amounts | 1 | yes |
| RS 00601 | PIA and Benefit Amounts - Introduction | 10 | yes |
| RS 00605 | Initial Computation of the PIA - Recomputations and Recalculations | 96 | yes |
| RS 00615 | Computation of Monthly Benefits Amounts | 95 | yes |
| RS 00620 | Computation, Recomputations, and Recalculations with Limited Applicability | 11 | yes |
| RS 00630 | Monthly Benefit Amount Computations with Limited Applicability | 6 | yes |
| RS 00640 | Computation and Benefit Tables - Old Law | 3 | yes |
| **RS 025** | Annual Earnings Test | 78 | 78 |
| RS 02500 | Annual Earnings Test | 1 | yes |
| RS 02501 | History | 20 | yes |
| RS 02505 | Variances in and Types of Earnings and Retirement | 42 | yes |
| RS 02510 | Annual Reports | 15 | yes |
| **GN 026** (GN 02603 only) | Posteligibility | 279 | 12 |
| GN 02603 | Readjustment Procedures | 12 | yes |

Part RS lists 1,667 sections in 17 chapters and part GN 4,159; the rest of both parts is
not taken.

### What the rows hold

Text retention was measured per page: the words of the page's `div.poms` text (dropped
selectors removed) against the words of its rows (document heading, block headings,
block bodies). RS keeps 99.2% of 279,333 words and GN 99.1% of 7,035. What is missing:

- Sub-headings with no text of their own, such as `C. Computing deduction before reduction
  for permanent deductions` over numbered blocks in GN 02603.050. No row carries them; the
  blocks under them keep their own headings.
- RS 02510.026: 57 `<pre>` screen exhibits (DEQY earnings-query printouts, 254 words). The
  HTML extractor reads heading, `p`, `li`, `table` and `blockquote` nodes
  (`documents._TEXT_TAGS`), not `pre`. No other page in either scope has a `pre` element,
  and no register-cited page has one.
- Exhibits that only link a form: RS 00605.390, .391 and .392 print "To view this form, go
  to SSA-150." (or SSA-58, SSA-308); RS 02510.030 D links Form SSA-L9790 as a PDF ("View In
  PDF"). The forms are not taken.

## Register check

Every one of the 24 `pending_texts` excerpts was matched against these scopes with the
proof-evidence matcher of axiom-encode at rulespec-us's pinned `axiom_encode_ref`
(`3bf5a2af`, `harness.proof_validator._source_contains_proof_evidence`). POMS sections
were composed the way `corpus_resolver._compose_descendant_text` composes a bodyless
document (each block as heading, blank line, body; blocks joined by a blank line); CFR
sections were read from their row body. 22 match. The two that do not are the 404.409(b)
table rows: the snapshot excerpts `Before 1/2/1912 62 years.` and
`1/2/1912—1/1/1940 65 years.` read as `Before 1/2/1912 | 62 years.` and
`1/2/1912—1/1/1940 | 65 years.` here, so the register cites them in that form when it
moves them to `texts`.

## Citation-path ratchets

Measured with `scripts/validate_citation_paths.py --update-baselines` over every locked
provisions file on `main` (2,330, hash-verified against their locks; main alone measures
exactly at the existing baselines) plus the three new files: `block_n` +2,584 (the POMS
`block-N` rows) and `uppercase_segments` +21 (eCFR `subpart-A` to `subpart-V`); the other
families are unchanged.

## Fit with the W6 successor release

The three scopes are meant to join `us-rulespec-2026-10-12-w6-successor-union` (PR #819,
selector at its head 4edda63e2, 1,446 scopes). A candidate selector of those 1,446 scopes
plus these three (1,449, built in scratch, not committed) was audited against the locked
provisions, inventories and coverage of every scope:

- `scripts/audit_release_scope_self_containment.py`: 0 residuals (the W6 selector alone: 0).
- `axiom-corpus-ingest validate-release --prefix provisions --prefix inventory --prefix
  coverage`: 0 errors, the same 562 warnings as the W6 selector alone (541
  `missing_parent_id`, 17 `unsectioned_document_body`, 4 `empty_provision_text`), none in
  these scopes. Under the selector's `complete-expression-dates-v1` profile the check
  requires release-wide citation uniqueness (`release_quality`, `duplicate_release_citation`),
  so no citation of these scopes is in another W6 scope.

## Not done here

Signing the ingest manifests and writing the scope locks are part of this PR. Cutting,
publishing and activating a release that carries the three scopes, and re-pinning
rulespec-us to it, are separate steps for the release owner. After that, rulespec-us moves
the register's affected `pending_texts` to `texts`.
