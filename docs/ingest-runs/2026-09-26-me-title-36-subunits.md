# Maine Title 36: complete section bodies, child provisions below the section, and MRS pension deduction forms (2026-09-26)

Two scopes for TheAxiomFoundation/rulespec-us#1419, the Maine pension income
deduction (36 M.R.S. §5122(2)(M-2) and its phase-out, (M-3)), whose step 1 is
this corpus work.

| scope | rows | coverage |
|---|---:|---|
| `us-me/statute/2026-09-26-income-tax-subunits-us-me-title-36` | 7,745 | complete, 7,745 / 7,745, 0 missing, 0 extra |
| `us-me/form/2026-09-26-me-pension-income-deduction-forms` | 6 | complete, 6 / 6, 0 missing, 0 extra |

Neither scope is published to R2, loaded into Supabase or added to a release
selector. Both carry signed ingest manifests.

## 1. Statute: every numbered unit of a Maine section

### Problem

`parse_maine_section` built a section body from `subsection.select_one(".mrs-text")`,
the first text node of each `.MRSSubSection`: the subsection's own lead-in. Every
unit below it (`.MRSLetteredPara`, `.MRSSubPara`, `.MRSDivision`,
`.MRSSubDivision`), every continuation paragraph inside a subsection, and every
section-level paragraph printed next to subsections were dropped. The released
row `us-me/statute/36/5122` in `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36`
(id `88f3606d-528a-5355-a8eb-3de153e6bc40`) is 495 characters, the lead-ins of
subsections 1 to 4, although the retained source page
(`title36sec5122.html`, SHA-256 `05d1f7f8…fdca`) prints 54,705 characters of
statute text, including (M-2) and (M-3). No row below the section existed, so
`us-me/statute/36/5122/2/M-2`, the path axiom-encode maps to
`us-me/statutes/36/5122/2/M-2.yaml`, could not resolve.

### How much text the 2026-09-14 scope lost

Measured line by line: each line the fixed parser produces from a retained page
is looked up in that section's 2026-09-14 body.

- 336 of the 1,776 section rows lack statute text their page prints: 3,707
  lines, 843,677 characters of text (847,384 with their line breaks). 996 bodies are unchanged; 440 change only because the
  amendment-history bracket no longer runs into the body of a section without
  subsections; 4 change only in layout (§§943 and 1075 print a form over
  several blocks, now several lines; §§1506 and 6661 had a Revisor's note
  inline, now only in `metadata.notes`).
- 246 sections print lettered paragraphs, and no lettered paragraph's text was
  in any 2026-09-14 body: 2,152 paragraph lines were missing, in 245 sections.
  The other 33 paragraph lines are placeholders that print only their number
  (such as "D."), which the old bodies happen to contain as a substring.
- By owner of the missing line:

| missing line | lines | sections | characters |
|---|---:|---:|---:|
| lettered paragraph (its first line) | 2,152 | 245 | 490,324 |
| subparagraph | 770 | 92 | 146,997 |
| division | 180 | 23 | 32,122 |
| subdivision | 27 | 3 | 5,027 |
| continuation paragraph inside a subsection | 228 | 112 | 78,607 |
| continuation paragraph inside a lettered paragraph | 158 | 32 | 39,930 |
| continuation paragraph inside a subparagraph | 15 | 9 | 4,423 |
| section-level paragraph printed next to subsections (e.g. §111's "As used in this Title, …") | 177 | 153 | 46,247 |

- The largest losses: §5122 (221 lines, 53,989 characters; 495 → 54,705),
  §5200-A (38,016), §191 (25,902), §176-A (25,893), §1760 (24,075), §1752
  (17,927). Appendix A lists all 336.
- rulespec-us#1419 reported a heuristic count of 222 sections "whose first
  lettered paragraph is missing"; its exact rule is not given. The first
  lettered paragraph's line is absent from 239 of the 246 sections that have
  one (the other 7 open with a number-only placeholder).

### What the source asserts

The Revisor's section pages mark each numbered unit with a class naming its level
in Maine's drafting hierarchy and print its number in a dedicated element:

| class | level | number printed in | Title 36 count |
|---|---|---|---:|
| `MRSSubSection` | subsection | `span.headnote` (`2. Subtractions.`) | 2,650 |
| `MRSLetteredPara` | paragraph | `span.letpara_id` (`M-2.`) | 2,185 |
| `MRSSubPara` | subparagraph | first `span` (`(1)`) | 770 |
| `MRSDivision` | division | first `span` (`(a)`) | 180 |
| `MRSSubDivision` | subdivision | first `span` (`(i)`) | 27 |

Units nest in that order (subsection > paragraph > subparagraph > division >
subdivision), sometimes inside an unnumbered continuation block
(`div.mrs-text.paragraph.B`, e.g. §5122(2)(M-3)'s "For purposes of this
paragraph, 'applicable amount' means:"). Sections without subsections print
`MRSIndentedPara` paragraphs (829 in Title 36). The statute's own cross
references use the same hierarchy ("paragraph M-2, subparagraph (1), division
(a)" in (M-3)). No other `MRS*` class occurs inside a Title 36 section. Every one
of the 5,812 units carries a number the adapter parses.

The Revisor sometimes prints two units with the same number under one parent.
Title 36 has 20 such groups: a live unit next to the placeholder of a repealed or
reallocated one (§5122(1)(KK), whose second KK was repealed by PL 2017, c. 211;
§191(2)(DD) with two "REALLOCATED TO" placeholders), and dated versions marked
"(TEXT EFFECTIVE UNTIL 1/05/26)" / "(TEXT EFFECTIVE 1/05/26)" (§§1811, 4362-A,
4365-F-1, 4366-A, 4401, 4641-A, 4641-B).

### Adapter change (`src/axiom_corpus/corpus/state_adapters/maine.py`)

- Section body. The section node is split into lines in document order: every
  block element and every numbered unit starts a line; inline elements (links,
  labels, table cells) stay in their line, joined as `get_text(" ", strip=True)`
  joins them, so each subsection lead-in line is byte-identical to the line the
  old parser produced. Amendment history (`.bhistory`, `.qhistory`), status blips
  and Revisor's notes stay out of the body, as they already did for sections
  with subsections; history and notes remain in `metadata.source_history` and
  `metadata.notes`. For sections without subsections this removes the
  "[PL …]" history bracket (and, in two sections, a Revisor's note) that the
  2026-09-14 fallback had printed inline.
- `metadata.source_history` now collects every `.bhistory` of the section in
  document order (it had skipped those outside subsections): 47 section rows
  gain entries and 33 list the same entries in document order.
- Child provisions (`include_subunits`). Each numbered unit becomes a row:
  citation path = section path + the chain of unit numbers
  (`us-me/statute/36/5122/2/M-2/1/a/i`); `kind` subsection, paragraph,
  subparagraph, division or subdivision; `citation_label` and
  `legal_identifier` `36 M.R.S. § 5122(2)(M-2)(1)(a)(i)`; `heading` the
  subsection headnote title (none below the subsection); `level` section level
  plus depth (4 to 8); `ordinal` the position among siblings; `parent_id` the
  enclosing unit or the section. Body: the unit's first line without its printed
  number (and, for a subsection, without its headnote), followed by every later
  line of the unit verbatim, descendants' numbers kept. Every child body is
  therefore a contiguous run of the section body, apart from its first line's
  label. Leading status parentheticals ("(TEXT EFFECTIVE UNTIL 1/05/26)",
  "(REALLOCATED TO T. 36, §5122, sub-§2, ¶T)", "(REALLOCATED FROM …)",
  "(FUTURE CONFLICT: …)") move from the child's first line to
  `metadata.notes`; they stay in the section body. `metadata.status` is
  `repealed` (a placeholder whose own history ends in "(RP)", or a
  "TEXT REPEALED" date on or before the expression date), `reallocated`,
  `effective-until`, or absent. `metadata` also carries `section`,
  `section_heading`, `publisher_label` (`M-2.`), `references_to` (links in the
  unit) and `source_history` (the unit's history spans). `identifiers` carry
  `maine:section`, one `maine:<kind>` per level and `maine:source_id`
  (`36-5122/2/M-2`).
- Same-number units. The unit in force on the expression date keeps the plain
  number: the first unit that is current and has text, else the first current,
  else the first with text. Every other unit gets a `--` variant slug through
  `citation_segment.variant_segment` (the NM/VT convention,
  `7-1-6.21--effective-2027-07-01`): `effective-until-YYYY-MM-DD`,
  `effective-YYYY-MM-DD` or `repealed-YYYY-MM-DD` from its dated marker, else
  `reallocated`, else `repealed` (placeholder with "(RP)" history), else
  `placeholder` or `duplicate`, with `-<printed position>` added when two
  variants of one group share a slug. Rows record `metadata.variant`,
  `variant_of` and, on the plain row, `variants`. Title 36 has 21 variant rows,
  for example `36/4401/2-A--effective-until-2026-01-05`,
  `36/5122/1/KK--repealed`, `36/5122/2/P--reallocated` and
  `36/191/2/DD--reallocated-2` / `-3`.
- `extract_maine_revised_statutes(..., include_subunits=False)`: the default
  keeps the section grain (with the corrected bodies); `extract-state-statutes`
  reads the manifest option `include_subunits`, default false, as it does for
  Wisconsin. `parse_maine_section(..., as_of=)` receives the expression date.

Blast radius. GitNexus could not be used: its index here is storage version 42
and the installed CLI reads version 40 (`impact` returned `risk: UNKNOWN` with
that error for both symbols). By text search, `parse_maine_section` is called only
by `extract_maine_revised_statutes` (through `_fetch_section_pages`) and the
Maine tests, and `extract_maine_revised_statutes` only by the
`maine-revised-statutes` branch of `extract-state-statutes` in `cli.py` and the
tests. The only other Maine statute scopes (`2026-07-03-me-tanf-statute`,
`2026-07-13-recovery`) come from the generic official-documents HTML extractor,
not this adapter, and are unaffected.

### Extraction

```bash
uv run axiom-corpus-ingest extract-state-statutes \
  --base data/corpus \
  --manifest manifests/us-me-statutes-title-36-subunits.yaml
```

The manifest reads the official pages retained, git-tracked, by the 2026-09-14
scope (`source_dir`; 1,923 pages: the statute index, the Title 36 page, 145
chapter pages and 1,776 section pages) and never touches the network, so the
new scope's sources are byte-identical copies and every difference from the
2026-09-14 rows comes from the parser. `source_as_of` and `expression_date`
stay 2026-09-14, the retrieval date of those bytes. The adapter appends
`-us-me-title-36`, giving version `2026-09-26-income-tax-subunits-us-me-title-36`.
Rows: 1 title, 11 parts, 145 chapters, 1,776 sections, 2,650 subsections, 2,185
paragraphs, 770 subparagraphs, 180 divisions, 27 subdivisions.

| artifact | SHA-256 | bytes |
|---|---|---:|
| `provisions/us-me/statute/2026-09-26-income-tax-subunits-us-me-title-36.jsonl` | `6a760b49aa58768c12dc3f02fd629759631c6d40ae89b9836bb71dfc8101916f` | 15,066,793 |
| `inventory/us-me/statute/2026-09-26-income-tax-subunits-us-me-title-36.json` | `c8321c76d87539589786f582414dbbe108b1d1537194e51d961b46ef563ce8d4` | 6,915,904 |
| `coverage/us-me/statute/2026-09-26-income-tax-subunits-us-me-title-36.json` | `1a0ccc987646920a50acf6adfbbf702787a564347fe0318ce3533126ce5a2aaf` | 353 |

### Target provisions

| citation path | kind | citation label | parent | body chars |
|---|---|---|---|---:|
| `us-me/statute/36/5122` | section | 36 M.R.S. § 5122 | `us-me/statute/title-36/chapter-805` | 54,705 |
| `us-me/statute/36/5122/2` | subsection | 36 M.R.S. § 5122(2) | `us-me/statute/36/5122` | 45,741 |
| `us-me/statute/36/5122/2/M-2` | paragraph | 36 M.R.S. § 5122(2)(M-2) | `us-me/statute/36/5122/2` | 3,395 |
| `us-me/statute/36/5122/2/M-3` | paragraph | 36 M.R.S. § 5122(2)(M-3) | `us-me/statute/36/5122/2` | 1,101 |
| `us-me/statute/36/5122/2/M-2/1/a/i` | subdivision | 36 M.R.S. § 5122(2)(M-2)(1)(a)(i) | `us-me/statute/36/5122/2/M-2/1/a` | 171 |
| `us-me/statute/36/5122/2/M-2/2/d/iv` | subdivision | 36 M.R.S. § 5122(2)(M-2)(2)(d)(iv) | `us-me/statute/36/5122/2/M-2/2/d` | 325 |

`5122/2/M-2` opens "For tax years beginning on or after January 1, 2016:" and
closes with (2)(f)'s "…subject to the tax imposed by the Code, Section 72(t);";
its history is "[PL 2025, c. 271, Pt. C, §2 (AMD); PL 2025, c. 452, §1 (AMD).]".
`5122/2/M-3` holds the phase-out sentence, the continuation "For purposes of
this paragraph, "applicable amount" means:" and subparagraphs (1) to (4)
($125,000; $187,500; $250,000; half of (3)). Section row ids are path-derived and
unchanged (§5122 keeps `88f3606d-…`).

### Verification

- `tests/test_corpus_maine.py` (38 tests):
  - §5122 from the retained bytes (SHA-256 pinned): 225 body lines,
    54,705 characters, the (M-2)(1)(a)(i) sentence, the (M-3) continuation
    and subparagraphs, no history bracket in the body, 205 units, the
    (M-2) body's first and last text and its history.
  - The same-number variants of §5122 (`1/KK--repealed`,
    `2/P--reallocated`), and a synthetic page of dated versions and
    reallocated placeholders read on 2026-09-14, on 2025-12-31 and with no
    date (the plain path follows the version in force).
  - Hypothesis property tests: 300 generated section pages (random nesting
    to subdivision, headnotes, continuation blocks inside or beside the
    children, history, notes, an intro paragraph). The body's words equal the
    generator's statute words in order and an independent string walk of the
    page; every generated unit comes back with its path, kind, heading and own
    words; each child body is a contiguous run of the section body; paths are
    unique; parents exist; sibling ordinals run 1..n; parsing is
    deterministic. 200 generated groups of same-number paragraphs: exactly one
    plain path, on the first unit with text; unique variant segments.
  - Every one of the 1,776 retained Title 36 pages: the same conservation and
    structure invariants, one subunit per unit element (5,812), and, per unit,
    a body equal to its own element's statute words minus exactly its printed
    number (a subsection's headnote) and leading status markers. Swapping two
    siblings' bodies fails this check (tried on §5122(2)(A)).
  - Review regressions (see Independent review): an impossible marker date
    (with and without child rows), an error page served without the section
    container, a headnote inside a Revisor's note, and parentheticals that
    open with a capitalised word but are not status markers ("(WHOLE milk
    only)", "(TEXT of the note)").
  - Replay: running the committed manifest against the retained bytes, with
    network access patched to fail, reproduces the provisions, inventory,
    coverage and all 1,923 source files byte for byte, and pins the target
    provisions above.
  - Differential check against the 2026-09-14 scope, inside the replay test:
    all 1,933 of its citation paths are in the new scope with the same id,
    heading, parent, kind and level. Title, part and chapter bodies are
    identical. Section metadata is identical except `source_history`, which is
    a superset. After the old inline history and note strings are set aside,
    each line of every old section body is still in the new body.
  - `include_subunits` defaults to the section grain. `extract-state-statutes`
    passes the option through: true for the new manifest, false for the
    `us-me-statutes` entry in `manifests/state-statutes.current.yaml` and the
    2026-09-14 chapter manifest.
- The superseded scope replays from its attested generator. `maine.py` at the
  commit its signed ingest manifest records (`dcdb4e424`, identical to this
  file on `origin/main` f1916d73b) regenerates its provisions, inventory and
  coverage from the same retained bytes with the manifest's recorded SHA-256
  (`4774a1ee…`, `5a85feea…`, `f1d9a297…`). Every difference between the two
  scopes therefore comes from this parser change.
- Independent re-implementation. A separate agent, which did not read the
  adapter's parsing code or the tests, wrote an `lxml.html` parser from a
  written specification of these rules and ran it over the 1,776 retained
  pages. Result: 1,776 section bodies and 5,812 child rows, with 0 mismatches
  in kind, heading, body, level, ordinal, parent and citation label. On 10
  variant pages it first cited the file-name section number, e.g.
  `4307-2`, where both the page heading and the committed rows cite §4307;
  it then counted that as its own specification gap. Deliberate mutations of
  its parser (keeping notes, treating tables as blocks, leaving markers in,
  ignoring the date when choosing the plain path, keeping status blips) each
  produced mismatches, so the clean result is not vacuous.
- Independent review (Subfleet, GPT-6 Astra, `--task review --tier hard`,
  job `20260927-005448-maine-754-review`) re-derived the counts, hashes and
  manifests above and reproduced four parser defects with synthetic pages,
  none present in the retained Title 36 pages; all four are fixed here and the
  committed scope is unchanged (the replay test still reproduces it byte for
  byte):
  - an impossible date in a status marker ("2/29/25") raised and dropped the
    whole section, even at the section grain; the marker is now kept in notes
    and the unit treated as undated;
  - a page with no `.MRSSection` or `.section-content` was read whole, so an
    error page served with HTTP 200 became a section body; now only the
    Revisor's statute-text elements count, and a page with none raises, so the
    extractor records it as an error instead of a row;
  - a `.headnote` inside a Revisor's note could number its subsection;
    labels and history inside notes are now ignored;
  - any parenthetical opening with `TEXT`, `WHOLE`, `CONFLICT` and similar was
    taken for a status marker and moved out of the child body; markers are now
    the Revisor's complete forms only (`TEXT EFFECTIVE …`, `TEXT REPEALED …`,
    `TEXT WITH CONFLICT`, `REALLOCATED TO|FROM …`, `[FUTURE] CONFLICT: …`,
    `[FUTURE] CONTINGENT REPEAL|TERMINATION|EFFECTIVE …`, `WHOLE SECTION TEXT …`,
    `REPEALED`).
  It also showed the retained-page invariant accepted two swapped sibling
  bodies, which the per-unit check above now rejects. A re-review of the fixes
  (job `20260927-011414-maine-754-rereview`) confirmed all four and the swap
  rejection, found every one of the 79 marker occurrences in the retained
  pages still recognised, regenerated all 1,926 artifacts with their committed
  hashes, and reproduced one more family: an element that is itself a note
  (`div.mrs-text.note` without a section container, `span.headnote.note`, a
  note before a subparagraph's number) could still become text or a label.
  Those are ignored now too, with tests. A third pass (job
  `20260927-012352-maine-754-final`) again regenerated all 1,926 artifacts with
  their committed hashes and reproduced further synthetic placements of
  apparatus: an apparatus class on a unit element itself, a note nested inside
  a printed number or history span, a section container or heading inside a
  note. Rather than patch each, one rule now applies throughout: an element is
  editorial if it, or an ancestor, carries any of the apparatus classes
  (`heading_section`, `headnote_blip`, `qhistory`, `bhistory`, `note`) other
  than the one being collected, and numbers, headings, history and blips are
  read without editorial descendants. Tests cover each apparatus class in each
  placement. None of these placements occurs in the 1,923 retained files. Its lane had no network,
  so the other-title check below was run in this session.
- Other titles (the section-body change applies to every title the adapter
  reads). 57 live pages fetched on 2026-09-27 at one request per second: the
  first two sections of three chapters in each of Titles 5, 12, 20-A, 22, 24-A,
  29-A, 35-A and 38 (48 pages), and 9 long ones (22 §§3104, 3174-G, 3762; 29-A
  §101; 38 §1303-C; 35-A §3201; 24-A §4320-D; 20-A §15671-A; 12 §10001). All
  pass the conservation, structure and per-unit checks: 1,351 units, depth up
  to 5, one same-number variant (22 §3174-G), and no `MRS*` class other than
  the five unit classes, `MRSIndentedPara` and `MRSSection`.
- rulespec-us (`origin/main` 54d90a725) cites six Title 36 sections (§§5111,
  5124-C, 5126-A, 5213-A, 5219-S, 5219-SS), all present under the same paths.
  Its 38 proof excerpts against them match the new bodies wherever they
  matched the old ones: 36 before, 36 after, 0 regressions. The other two
  (§5219-S, whose body is unchanged) match neither.
- `scripts/validate_citation_paths.py` over the whole provisions tree: OK
  after raising the `uppercase_segments` baseline from 16,280 to 20,490. The
  new scope adds 4,210 unique uppercase paths, because Maine writes section
  suffixes and lettered paragraphs in capitals (`5219-SS`, `M-2`), and the
  official number is the segment. Every other family is at its baseline.
- `validate-release` on a scratch selector (not committed): the 22 `us-me`
  scopes of `us-rulespec-2026-09-14-wave4-r2-union` with the 2026-09-14
  Title 36 scope swapped for this one and the forms scope added, 23 scopes,
  gives 0 errors and 212 `empty_provision_text` warnings (the placeholders
  under Known limitations). The same 22 scopes unswapped give 0 errors and
  0 warnings.

## 2. Form: Maine pension income deduction documents (TY2025 and TY2026)

`manifests/us-me-pension-income-deduction-forms.yaml` follows the Wisconsin
Schedule SB pattern (`manifests/us-wi-2025-schedule-sb-instructions.yaml`,
section 2 of `docs/ingest-runs/2026-09-23-wi-chapter-71-subunits.md`): three
official PDFs, `segmentation: single_block`, `document_class: form`, one scope.
The citation paths take the state-form shape `us-xx/form/<agency>/ty<year>/<id>`
of `scripts/build_tax_forms_manifests.py` and the `2026-09-14-ty2026-indexed-amounts`
scopes (`us-ct/form/drs/ty2026/ct-1040es`, `us-ia/form/idr/ty2026/ia-1040es-instructions`);
Maine had no `form` row before this scope (its released MRS rate schedule is
`us-me/guidance/revenue/individual-income-tax/2026/rate-schedules`), so the
agency slug is the acronym `mrs` (Maine Revenue Services), as `ador`, `cdor`,
`drs`, `idr`, `istc`, `otc`, `trd` and `vdt` are in that family. Requested by
TheAxiomFoundation/rulespec-us#1419 (36 M.R.S. §5122(2)(M-2) encoding).

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-09-26-me-pension-income-deduction-forms \
  --manifest manifests/us-me-pension-income-deduction-forms.yaml
```

Report: 3 documents, 3 blocks, 6 provisions, coverage `complete: true`
(`matched_count` 6, `missing_from_provisions` 0, `extra_provisions` 0).

### Documents

Retrieved 2026-09-26 (America/New_York; the publisher's `Date` headers read
2026-09-27 03:01 to 03:04 GMT) from www.maine.gov with the corpus user agent,
HTTP 200, no redirect, `Content-Type: application/pdf`. Every SHA-256 equals the
value recorded in rulespec-us#1419.

| citation path | title | source URL | bytes | pages | SHA-256 | HTTP `Last-Modified` | PDF `CreationDate` |
|---|---|---|---:|---:|---|---|---|
| `us-me/form/mrs/ty2026/1040es-me` | 2026 Form 1040ES-ME Instructions – Estimated Tax for Individuals (Revised: July 2026) | <https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/26_1040es_fillable.pdf> | 1,633,438 | 6 | `2b4a9b22a77d096a47fd4d4cb0b9fd2255d773ea7b9123a8a9b86d519730275c` | Fri, 17 Jul 2026 20:03:08 GMT | 2026-07-17 16:00:31 EDT |
| `us-me/form/mrs/ty2025/1040me-schedule-1s` | 2025 Form 1040ME Schedule 1S – Income Subtraction Modifications (attachment sequence no. 5) | <https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/25_1040me_sch_1s_fillable.pdf> | 3,587,877 | 2 | `f158b7ef00c8f1bc27c8c35a65d5478dd410804b30afb20f279e3a81d9e5ca0a` | Wed, 14 Jan 2026 18:03:10 GMT | 2026-01-14 12:42:35 EST |
| `us-me/form/mrs/ty2025/1040me-instructions` | 2025 Form 1040ME Instructions – Maine Resident Individual Income Tax Booklet (with MRS conformity cover page) | <https://www.maine.gov/revenue/sites/maine.gov.revenue/files/inline-files/25_1040me_gen_instr_w_cover_pg.pdf> | 473,431 | 13 | `00f731e053a19cc464595fbf38d61e11daa1e3e5a7bed525708a12d9b426051d` | Wed, 07 Jan 2026 15:37:23 GMT | 2025-12-16 10:22:36 EST |

Sources are retained at
`sources/us-me/form/2026-09-26-me-pension-income-deduction-forms/official-documents/us-me-mrs-{1040es-me-ty2026,1040me-schedule-1s-ty2025,1040me-instructions-ty2025}.pdf`.
`pdfinfo` reports the 1040ES-ME and Schedule 1S files as AcroForm (fillable)
PDFs and the instructions as a non-form PDF; all three are PDF 1.6, letter size.

### Rows

Six rows: each document root (`kind: document`, level 1, no body) and its
`.../document-1` child (level 2) holding the whole text layer.

| row | id | body |
|---|---|---:|
| `us-me/form/mrs/ty2026/1040es-me` | `45bbfdc3-dd67-5511-b5dd-6017d6533dc7` | – |
| `us-me/form/mrs/ty2026/1040es-me/document-1` | `b14dfbff-eeb5-5234-bc9a-08f6e947fe2c` | 16,785 characters (6 pages) |
| `us-me/form/mrs/ty2025/1040me-schedule-1s` | `69c82960-d79d-5c17-8279-ffcb1c2f5d3c` | – |
| `us-me/form/mrs/ty2025/1040me-schedule-1s/document-1` | `6577f996-68b9-520c-9a0a-76652f31e723` | 9,482 characters (2 pages) |
| `us-me/form/mrs/ty2025/1040me-instructions` | `9247c7c4-8fcb-57b0-aa4a-0d69b23a69f1` | – |
| `us-me/form/mrs/ty2025/1040me-instructions/document-1` | `cdd22827-0ef4-55d1-8e8d-f11af2da0816` | 90,670 characters (13 pages) |

`source_as_of` 2026-09-26 (retrieval) on every row; `expression_date`
2026-01-01 on the 1040ES-ME rows and 2025-01-01 on the Schedule 1S and
instructions rows (tax year), as the WI Schedule SB (2025-01-01) and CT-1040ES
(2026-01-01) manifests set them. The manifest sets both dates per document.

### Key statements (checked against `pdftotext -layout` and the row bodies)

Each statement below is in the PDF text layer at the stated page and in the
corresponding `document-1` body verbatim after whitespace normalization.

- 2026 Form 1040ES-ME, page 2, "2026 ESTIMATED TAX WORKSHEET", line 2
  ("Deduct - income subtraction modifications included in line 1. See the 2025
  Form 1040ME, Schedule 1S."): "Note that the maximum pension income deduction
  is increased to $49,824 for tax year 2026." and "The maximum pension income
  deduction is equal to the annual social security benefit for an individual at
  the retirement age, as defined in 42 USC § 416(l), as of January 1, 2026."
  The string `49,824` occurs once in the body.
- 2025 Form 1040ME Schedule 1S, page 2, "Worksheet for Pension Income
  Deduction - Schedule 1S, Line 4": line P2 "Maximum allowable deduction"
  prints `48,216.00` in both the Taxpayer and Spouse columns; line P3 is "Total
  social security and railroad retirement benefits you received - whether
  taxable or not"; line P4 subtracts P3 from P2 (if zero or less, enter zero);
  line P5 is the smaller of P1 or P4. The worksheet CAUTION names the phase-out
  thresholds $125,000 (single or married filing separately), $187,500 (head of
  household) and $250,000 (married filing jointly or qualifying surviving
  spouse) for Form 1040ME, line 14. The string `48,216` occurs twice in the
  body.
- 2025 Form 1040ME instructions, page 8, Schedule 1S line 4: "Enter the pension
  income deduction from the Pension Income Deduction Worksheet, line P10.
  Include copies of your 1099 forms to verify the subtraction. Enclose
  worksheet. 36 M.R.S. § 5122(2)(M-2)." and "The $48,216 cap must be reduced by
  any social security and railroad retirement benefits received, whether
  taxable or not." The string `48,216` occurs three times in the body (the
  third in the surviving-spouse sentence on the same page). Page 1 of this file
  is an MRS "IMPORTANT UPDATE" cover page on federal conformity (Maine conforms
  to the Code as of December 31, 2024; Public Law 119-21 changes pending before
  the 132nd Legislature's Second Regular Session).

### Replay

The same command run with `--base /private/tmp/claude-501/maine/forms-replay`
re-downloaded the three PDFs and reproduced the provisions, inventory and
coverage files and the retained sources byte for byte (`cmp` on each of the
three JSON/JSONL files and `diff -r` on the sources directory reported no
difference).

### Checks

| check | result |
|---|---|
| `uv run python scripts/validate_citation_paths.py --provisions <scratch tree holding only the new provisions file under us-me/form/>` | RESULT: OK; 6 records, 6 unique paths; irregular families all 0 (`block_n` 0, `page_n` 0, `space_segments` 0, `endash_segments` 0, `uppercase_segments` 0, `truncated_segments` 0, `collection_roots` 0) |
| `uv run --extra dev python -m pytest -q tests/test_corpus_documents.py` | 104 passed, 6 warnings |

No adapter, CLI, schema or test code was changed for this scope. The four
artifacts sit under `data/`, which `.gitignore` line 83 ignores (the tracked WI
Schedule SB artifacts sit there too); `git add -n -f` on the provisions,
inventory, coverage and sources paths lists all six files, and a plain
`git add -n` refuses them, so staging needs `-f`.

### Certification

Metadata on every row records `primary_source: true`, `source_authority: Maine
Revenue Services`, the file's `source_sha256`, `tax_year`, the line statements
above, `final_return_certification: false`, `rulespec_semantics: not_asserted`
and `policyengine_parity: not_asserted`. The intake preserves the official
documents and the MRS-published deduction amounts; it does not certify
final-return liability, RuleSpec semantics or PolicyEngine parity, and it does
not state the indexed TY2026 phase-out applicable amounts, which none of the
three documents prints.

## Release selection

A later named release that should carry these rows selects

```json
{"jurisdiction": "us-me", "document_class": "statute", "version": "2026-09-26-income-tax-subunits-us-me-title-36"},
{"jurisdiction": "us-me", "document_class": "form", "version": "2026-09-26-me-pension-income-deduction-forms"}
```

and drops `{"us-me", "statute", "2026-09-14-income-tax-chapter-us-me-title-36"}`,
whose 1,933 paths the new scope carries with the same ids. Profiled releases
(`complete-expression-dates-v1`) reject a citation path owned by two scopes. A
release line that still carries `us-me/statute/2026-07-13-recovery` instead
(for example `us-rulespec-2026-09-24-snap-fy2027-cola`) swaps it the way the
2026-09-14 note did: its six section paths collide, and rulespec-us cites its
`36/5111/block-2`, which neither Title 36 scope has. rulespec-us then re-pins
`axiom_corpus_ref` (rulespec-us#1419 step 1.4).

## Known limitations (not changed here)

- Tables are flattened into their line, cell by cell, as before
  (36 M.R.S. §5111's rate tables read "If Maine taxable income is: The tax is:
  Less than $4,150 2% of the Maine taxable income …"). A row-per-line rendering
  would change released section bodies and belongs in a separate change.
- Text on either side of a link is joined with a space, as before
  ("paragraph M-2 , subparagraph (1)", "section 5164 .").
- 480 child rows have no body: placeholders the Revisor prints with a number
  and amendment history but no text. 268 are subsections whose headnote title
  is their heading; the other 212 (209 repealed and 3 reallocated paragraphs)
  have neither body nor heading, so `validate-release` reports
  `empty_provision_text` warnings for them.
  They are kept because the source asserts them and their status and history
  tell a citing module the paragraph is repealed.
- 36 M.R.S. §4831(1) prints only its headnote ("1. Brown good.").

## Checks

| check | result |
|---|---|
| `uv run --extra dev ruff check .` | all checks passed |
| `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports` | no issues in 93 source files |
| `pytest tests/test_corpus_maine.py tests/test_corpus_cli.py tests/test_ingest_manifest_provenance.py tests/test_citation_path_grammar.py` | 170 passed (38 Maine) |
| `pytest tests/test_corpus_documents.py` (forms scope) | 104 passed |
| `python scripts/validate_citation_paths.py` | OK (see Verification) |
| `towncrier check --compare-with origin/main` | the three fragments found |

The whole-repository `pytest -q` run is left to CI. `hypothesis` is added to the
`dev` extra; CI installs `.[dev]` with pip, and `uv.lock`, which CI does not
use and which is already out of date with `pyproject.toml` on `origin/main`, is
left untouched.

## Remaining controller steps

Release selection, dry-run, publish and activation, then the rulespec-us
re-pin, as usual; none is done here. Per AGENTS.md this state-statute scope is
not merged to `main` without an explicit publication instruction.

## Appendix A: the 336 section rows of the 2026-09-14 scope that lacked statute text

By citation-path segment under `us-me/statute/36/` (a `-1`/`-2` suffix is the
Revisor's second page for one section, e.g. `4307-2` is a version of §4307):
111, 112, 113, 141, 144, 151, 151-A, 151-C, 151-D, 172, 173, 175-A, 176-A, 176-B, 182, 185-A, 187-B, 191, 193, 194-D, 199-A, 199-B, 199-C, 200, 208-A, 209, 271, 272, 272-A, 303, 305, 306, 310, 314, 327, 328, 329, 330, 383, 457, 472, 473, 474, 501, 505, 507, 508, 559, 573, 574-B, 574-C, 578, 581, 581-G, 603, 612, 651, 652, 653, 654-A, 655, 656, 661, 681, 682, 683, 685, 691, 692, 693, 694, 700-A, 706-A, 707, 841, 942-A, 943-C, 944, 945, 946, 946-C, 949, 996, 1102, 1106-A, 1109, 1112-C, 1132, 1135, 1137, 1138, 1481, 1482, 1483, 1484, 1486, 1487, 1495, 1502, 1503, 1504, 1602, 1603, 1604, 1608, 1611, 1752, 1754-B, 1760, 1760-D, 1765, 1811, 1815, 1819, 1951-C, 2012, 2013, 2014, 2015, 2016, 2020, 2021, 2022, 2513-C, 2521-E, 2523, 2524, 2525, 2525-A, 2529, 2532, 2621-A, 2625, 2724, 2726, 2852, 2853, 2854, 2855, 2856, 2857, 2857-A, 2859, 2862-A, 2871, 2872, 2873, 2881, 2891-A, 2893, 2902, 2903, 2903-D, 2906, 2906-A, 3202, 3203, 3204-A, 3204-B, 3209, 3219-A, 4043, 4062, 4063, 4063-A, 4064-A, 4068, 4069, 4071, 4102, 4103, 4107, 4108, 4111, 4302, 4305, 4307-2, 4311-A, 4312-C, 4314, 4315, 4361, 4362-A, 4365-F-1, 4365-G, 4366-A, 4366-B, 4366-C, 4372-A, 4373-A, 4401, 4402, 4403-1, 4403-2, 4403-A, 4404-A, 4404-B-2, 4404-C, 4602, 4603, 4604, 4605, 4606, 4641, 4641-A, 4641-B, 4641-C, 4641-D, 4641-K, 4711, 4831, 4901, 4902, 4921, 4922, 4923-1, 4923-2, 5102, 5111, 5122, 5124-B, 5124-C, 5125, 5126, 5126-A, 5132, 5142, 5176, 5192, 5195, 5196, 5197, 5200, 5200-A, 5200-B, 5202-D, 5202-E, 5203-C, 5206, 5206-D, 5206-E, 5210, 5211, 5213-A, 5215, 5216-B, 5217, 5217-C, 5217-D, 5217-E, 5218-A, 5219-AAA, 5219-BB, 5219-BBB, 5219-DD, 5219-FF, 5219-GG, 5219-H, 5219-HH, 5219-II, 5219-JJ, 5219-KK, 5219-LL, 5219-MM, 5219-NN, 5219-O, 5219-OO, 5219-PP, 5219-Q, 5219-QQ, 5219-R, 5219-RR, 5219-SS, 5219-VV, 5219-W, 5219-WW, 5219-XX, 5219-YY-2, 5219-ZZ, 5220, 5221, 5227-A, 5228, 5250, 5250-A, 5250-B, 5253, 5265, 5278, 5279, 5283-A, 5287, 5295, 5332, 5402, 5403, 6201, 6206, 6207, 6232, 6234, 6235, 6250, 6251, 6252, 6252-A, 6253, 6254, 6258, 6259, 6260, 6261, 6262, 6263-2, 6264, 6271, 6281, 6572, 6582, 6583, 6592, 6602, 6612, 6613, 6651, 6652, 6656, 6753, 6754, 6755, 6756, 6760, 6764, 6901, 7122, 7126.
