# `pre` elements in official-document HTML: the gap and the fix

Date: 2026-10-12
Branch: `fix/html-pre-extraction`, cut from `origin/main` (`2b9ca4ba2`).
Measured with `scripts/audit_html_pre_gap.py`; no scope is re-extracted here.

## Why

`documents._extract_html_blocks` read only heading, `p`, `li`, `table` and `blockquote`
nodes (`documents._TEXT_TAGS`). Text in a `pre` element reached a row in one of three
ways only:

- it sat inside one of those tags, which read it through their own text;
- the manifest named it in `html_text_selector`;
- the page had no other text node, so the extractor fell back to the whole content
  root (`root.get_text`), joining every line with spaces.

Otherwise it was dropped, and coverage still read `complete` because coverage compares
inventory with rows, not page text with rows. The POMS ingest in
TheAxiomFoundation/axiom-corpus#826 found this on RS 02510.026: 57 `pre` screen exhibits
(DEQY earnings-query printouts) were in no row.

## Method

```bash
uv run python scripts/audit_html_pre_gap.py --baseline-ref 2b9ca4ba2 \
  --ref origin/ingest/ssa-oasdi-source-conflict-texts --all --workers 4 \
  --output <report.json>
```

- **Sources:** every official-document source with an `.html`, `.htm`, `.xhtml` or
  `.json` path in every lock. That is 16,140 sources in 536 scopes on `main`, plus
  the 470 POMS RS and GN sources of #826 (`--ref` reads that branch's locks and
  manifests). Total: 16,610 sources in 538 scopes.
- **Bytes:** read from the shared corpus cache, hash-checked against the lock. Nothing
  is placed under `data/corpus`. 157 locked files (5,087,454 bytes, 11 small scopes)
  were not in the cache. `corpus fetch --path` filled them before the run; every other
  object was already cached, so no publisher or family had to be sampled.
- **Configs:** each source is replayed through the extractor at `2b9ca4ba2` under every
  manifest entry that could have produced it: same jurisdiction, document class and
  `safe_segment(source_id)`, in every version of every manifest here and at `--ref`.
  An entry whose replay equals the locked rows (kind, heading and body, in order) is a
  verified config. Every one of the 61 sources that hold a `pre` element has one. None
  is ambiguous, meaning none has two verified configs that disagree on the patched
  output.
- **Gap:** the gap is the words in outermost `pre` elements under the content root
  (after the default and manifest drop selectors and `html_content_selector`) whose
  text no single locked row holds in its heading or body. Each `pre` is read the way
  the patched extractor reads it, so a `br` separates words. The test ignores
  whitespace, so it reads `ab` and `a b` as the same text.
- **Change:** the current extractor is replayed under the same config, and its blocks
  (kind, heading, body, metadata) are compared with the baseline replay. `--all` also
  compares every source without a `pre`.
- **Run:** 2 minutes 50 seconds at 4 workers.

## Results

61 of 16,610 sources hold a `pre` element, in 17 scopes. 15 of them, all on Colorado
and Rhode Island pages, have it only outside the content root: an empty debug `<pre>`.

| scope | sources with `pre` | `pre` under root | words | words no row holds | sources gaining text | sources changed | rows changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `us/manual/2026-09-13-ssi-poms-si-remainder` | 4 | 254 | 4,726 | 2,915 | 4 | 4 | 10 |
| `us/manual/2026-09-10-ssi-poms-si` | 9 | 175 | 1,551 | 314 | 4 | 9 | 9 |
| `us-sc/statute/2026-10-06-w6-income-tax-statute-sc` | 1 | 1 | 291 | 291 | 1 | 1 | 1 |
| `us/manual/2026-10-12-oasdi-poms-rs` (#826) | 1 | 57 | 254 | 248 | 1 | 1 | 3 |
| `us/manual/2026-09-13-medicare-poms-hi` | 2 | 41 | 242 | 242 | 2 | 2 | 2 |
| `us-wa/manual/2026-07-21-wa-eaz-manual` | 16 | 16 | 48 | 48 | 16 | 16 | 16 |
| `us-ga/manual/2026-09-11-ga-snap-manual-supersede` | 3 | 3 | 12 | 12 | 3 | 3 | 26 |
| `us/guidance/2026-09-13-medicare-annual-notices-2026` | 3 | 3 | 16,530 | 0 | 0 | 3 | 3 |
| `us-ny/statute/2026-10-06-w6-benefits-statute-ny` | 2 | 2 | 113,861 | 0 | 0 | 2 | 2 |
| `us/guidance/2026-09-10-wic-fns-guidance` | 2 | 2 | 3,195 | 0 | 0 | 2 | 2 |
| `us-ny/statute/2026-10-06-w6-income-tax-statute-ny-r2` | 1 | 1 | 96,290 | 0 | 0 | 1 | 1 |
| `us/guidance/2026-07-05-ssa-cola-2026` | 1 | 1 | 6,061 | 0 | 0 | 1 | 1 |
| `us/guidance/2026-09-13-liheap-annual-figures-2026` | 1 | 1 | 1,190 | 0 | 0 | 1 | 1 |
| `us-co/guidance/2026-10-06-w6-health-guidance-co` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| `us-co/guidance/2026-10-06-w6-income-tax-guidance-co` | 7 | 0 | 0 | 0 | 0 | 0 | 0 |
| `us-co/policy/2026-07-21-co-snap-policy` | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| `us-ri/guidance/2026-10-06-w6-income-tax-guidance-ri` | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

### The gap: 4,070 words in 31 sources

- **POMS, 3,719 words in 11 sources.** These are exhibits printed in `pre`:
  - SI 01210.300 (102 blocks, 1,726 words) holds a sample Notice of Planned Action.
  - SI 02101.008 (40 of its 131 `pre` blocks, 1,096 words) holds sample notices to
    survivors. The other 91 of its `pre` blocks are inside tables and were already
    read.
  - SI CHI00830.111 (243 words) is Indiana's sample letter notifying the AFDC agency;
    CHI00830.122 (37 words) is part of Ohio's CDHS/SSA inter-agency referral form.
  - SI 02310.062 (65 words) holds the S2 state wage-match discrepancy listing.
  - SI SF02005.082 (27 words) holds a freeze-conversion record instruction.
  - SI CHI01730.010 (28 words) holds Wisconsin's fax cover sheet for the State SSI
    cash unit.
  - SI SEA00830.403 (7 words) is the title of the Alaska need and payment standards
    table.
  - HI 00825.110 and 00825.907 (242 words) hold HIM and MBR query reply screens.
  - RS 02510.026 (248 words) holds the DEQY printouts. 54 of its 57 `pre` blocks are in
    no row; the other three repeat text a row already holds.
- **South Carolina, 291 words.** The history-of-legislative-actions table on the bill
  page for 2021-2022 H. 1087 is one `pre`. It is bill history, not statute text.
- **Georgia SNAP manual, 12 words.** The "Codes and References" section of 3350, 3355
  and 3360 is an AsciiDoc literal block (`7 CFR § 273.7`, `7 CFR § 273.24` and
  `7 CFR § 273.7(a)`). That heading had no text of its own, so no block was made for
  it.
- **Washington EA-Z, 48 words.** Each of 16 pages ends with
  `<pre><strong><a href="#Top">Top of Page</a></strong></pre>`. This is page
  furniture, not manual text.

The gap is material: 3,719 words of SSA manual text in three released POMS scopes and in
#826 were missing while coverage read complete. The same pattern recurs across POMS
exhibits, so every later POMS ingest would inherit it. The extractor change is below.

### Text already in rows, reformatted: 15 sources

- **Federal Register text notices, 7 sources.** These are the SSA 2026 COLA notice, the
  two WIC income-eligibility notices, the HHS 2026 poverty guidelines and the three CMS
  2026 Medicare notices. Each page is one `pre` and reaches its row through the root
  fallback, as before. Re-extracted, the body keeps its line breaks. Words differ by −2
  to −4 per notice, because the old fallback's `get_text(" ", strip=True)` added a
  space at every inline tag (`[ www.gpo.gov ]`, `index.html .`); the patched text reads
  as printed.
- **New York bills, 3 sources.** S7148 (2021), S3006 and S3009 (2025) set
  `html_text_selector: pre`, so their text was always read. The patched text keeps line
  breaks and drops the inline-tag spaces (`[ for the` becomes `[for the`). That
  accounts for 52, 874 and 405 fewer tokens; no text is lost.
- **POMS exhibit-only pages, 5 sources.** SI CHI00830.107, .117, .121, .123 and .129
  hold only an `h1` and `pre` blocks, so they reach rows through the root fallback, as
  before. Re-extracted, the row gains line breaks; the heading and every word are the
  same.

Every changed source keeps its row count except the three Georgia pages. Each gains a
block for "Codes and References", which shifts the `block-N` path of every later block
(26 rows change, 23 of them in heading because of the shift).

### Sources without `pre`: unchanged

Under every candidate config, the 16,450 replayable sources without a `pre` element give
the same blocks (kind, heading, body, metadata) from the patched extractor as from
`2b9ca4ba2`. That includes 13 sources whose manifests no longer reproduce their locked
rows, which are compared under every candidate anyway. The figure excludes:

- 72 CRA and Revenu Québec sources whose rows are locked with `source_format: text`,
  which `_extract_blocks` refuses in both versions (this extractor did not make them);
- 27 sources with no locked rows.

The patched extractor raised on no source that the baseline read.

## The change

- `pre` is a text node (`_PREFORMATTED_TAGS`, part of `_TEXT_TAGS`). A `pre` inside a
  `table`, `li` or `blockquote` is still read once, through that ancestor, and a text
  tag or `pre` inside a `pre` is read once, through the outer `pre`.
- `_html_node_text` reads a `pre` as printed:
  - no separator is added at inline tags;
  - each `br` is a line break. The newline is inserted and the `br` unwrapped, because
    html.parser nests the strings after `<br>` inside it.
  - `_normalize_preformatted_text` collapses whitespace within each line, keeps one line
    break between lines and one blank line between paragraphs, and drops leading and
    trailing blank lines.

  `_normalize_text` of the result equals `_normalize_text` of the input, character for
  character except where a line break became a space. Every other node reads as before.
- **Root fallback.** A page whose only body text nodes are `pre` (Federal Register text
  notices, exhibit-only POMS pages) still reaches its row through the root fallback, so
  text outside every text tag stays in the row. `_html_root_text` reads the root as
  the fallback always did, joining stripped strings with spaces, except that each
  outermost `pre` keeps its line breaks and sits between line breaks. `_normalize_text`
  of that text is the old fallback text. A manifest that sets `html_text_selector`
  keeps its old rule: blocks whenever a selected node has text.
- Block and labeled-section bodies join their node texts with a blank line and do not
  normalize them again (`_join_html_text_parts`). For parts that `_normalize_text`
  made, that is the same string as before, a property the tests check.
- **Labeled sections.** Label and stop patterns still match the flattened text. A body
  the section pattern captures from a `pre` is cut at the same span of the
  line-preserving text, so it keeps its line breaks too.
- **Content root.** A `pre` encloses other nodes only within the content root (the root
  itself included). A root that is a `pre` is read whole, with its line breaks. A root
  that sits inside a `pre` reads its nodes as before.
- `scripts/audit_recovery_sibling_scopes.py` (`read_page`, `_matching_run`) uses the
  same helpers, so it keeps walking pages the way the extractor does. None of its July
  recovery scopes has a `pre` page, so its committed audit is unchanged.
- The anchor-range, WebWorks and JSON single-block paths are unchanged. Anchor ranges
  already read `pre` text, flattened.

Line breaks and the encoder: axiom-encode's proof matcher
(`harness.proof_validator.collapse_evidence_whitespace`, read at its `main` on
2026-10-12) reads a single ordinary line break (`\n`, `\r\n` or `\r`) as a space. It
reads a blank line, or any run holding U+2028, U+2029, a form feed, a vertical tab or
NEL, as a paragraph gap. `_normalize_preformatted_text` splits lines with
`str.splitlines`, so those separators become ordinary line boundaries and the patched
text holds only `\n`. A line-preserved `pre` therefore matches the same excerpts as its
flattened form, apart from the inline-tag spacing above. The one rulespec citation of a changed document
found in the cloned rulespec repos still matches the patched body (checked against
rulespec-us `4b35d0872`, rulespec-us-ga, rulespec-us-ny and rulespec-us-sc; rulespec-us-wa
is not cloned here). That citation is rulespec-us `us/statutes/42/416/l.yaml` →
`us/guidance/ssa/cola/2026/federal-register/block-1`, excerpt "are exactly 12 times the
monthly"; its line break falls inside the excerpt.

## Follow-up for the Axiom eng hub: successor versions

Released scopes stay as they are. These are what re-extraction with the patched
extractor would change; each needs a signed successor version to carry the change into
a release.

Successors that add missing text:

1. `us/manual/2026-09-13-ssi-poms-si-remainder`: 4 sources, +2,915 words (SI 01210.300,
   02101.008, 02310.062, CHI01730.010). In 6 named releases.
2. `us/manual/2026-09-10-ssi-poms-si`: 4 sources gain 314 words (CHI00830.111, .122,
   SEA00830.403, SF02005.082); 5 exhibit-only pages gain line breaks only. In 8 named
   releases.
3. `us/manual/2026-09-13-medicare-poms-hi`: 2 sources, +242 words (HI 00825.110,
   00825.907). In 6 named releases.
4. `us-ga/manual/2026-09-11-ga-snap-manual-supersede`: 3 sources, +12 words (the
   "Codes and References" citations). The new block renumbers every later `block-N`
   path on those pages; no rulespec citation in the repos checked points at them. In 7
   named releases.
5. `us-sc/statute/2026-10-06-w6-income-tax-statute-sc`: 1 source, +291 words of
   legislative history on a bill page. A successor adds bill history, not statute text,
   so this one can wait for any other reason to cut the scope. In 2 named releases.

Re-extract only with a manifest change:

6. `us-wa/manual/2026-07-21-wa-eaz-manual`: the only text the patch adds is the
   "Top of Page" link in 16 pages. Re-extracting this scope as it stands would add page
   furniture, so give its manifest a drop selector for that `pre` first. Without
   another reason, cut no successor. In 17 named releases.

Reformat only (no text added, no successor needed):

7. Federal Register notices: `us/guidance/2026-07-05-ssa-cola-2026` (42 named releases),
   `us/guidance/2026-09-10-wic-fns-guidance`, `us/guidance/2026-09-13-liheap-annual-figures-2026`
   and `us/guidance/2026-09-13-medicare-annual-notices-2026`.
8. New York bills: `us-ny/statute/2026-10-06-w6-benefits-statute-ny` and
   `us-ny/statute/2026-10-06-w6-income-tax-statute-ny-r2`. A later cut of any of these
   gets line breaks and loses the inline-tag spaces. Before cutting one, check verbatim
   excerpts that quote a spaced form such as `index.html .`.

Not yet released:

9. `us/manual/2026-10-12-oasdi-poms-rs` (#826, handed to the eng hub, which folds it
   into the #819 release): re-extract this scope once this lands, before it is
   released, so its first version carries RS 02510.026's 248 words.
