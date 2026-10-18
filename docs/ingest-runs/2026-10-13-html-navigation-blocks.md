# HTML navigation blocks: the extractor filter and what successors would drop

Date: 2026-10-13. Branch `fix/html-navigation-blocks`, cut from #847
(`feat/withdrawn-scopes-content-checks`, e076a2648), whose release content
baseline records 1,198 `navigation_body` rows in 148 locked scopes (182 scopes
have a finding of some kind). Most are site menus, breadcrumbs and related-link
lists that the shared official-document HTML extractor wrote as `block-N` rows.

This change makes the extractor drop such blocks in future ingests
(`content_quality.is_navigation_block`, called from
`documents._extract_html_blocks`; rule in
[release-gate-policy.md](../release-gate-policy.md#the-extractor-drops-navigation-blocks)).
Every merged scope is unchanged. Nothing was fetched from publishers, published,
loaded or activated; the measurement below re-extracts the retained bytes the
scopes' locks pin into scratch output outside `data/corpus`.

## The rule, and why it is stricter than the check

The check flags a body when navigation strings cover 70% of its characters with
at most 25 words left over. Taken alone, that rule would delete text. Among the
flagged rows:

- the Connecticut income tax regulations hold ten repealed sections whose whole
  text is "Repealed April 6, 2000." followed by a "Return to Table of Contents"
  link. They are flagged because "Repealed" is also link text on the page;
- the North Dakota SNAP manual defines "Work Registration" inside a glossary
  link, so the definition is one navigation string;
- Georgia's Medicaid manual and Iowa's expanded instructions give a section's
  whole text as a pointer ("Refer to 2327 Property Essential to Self-Support.",
  "See reciprocal agreement").

So the extractor drops a positional block only when the check flags it **and**
every token lies in a navigation string or is only link separators (`|`, `>`,
`»`, `•` ...), the body is at least two such strings, none of them is longer than
12 words, and none ends a sentence. Nothing is dropped from a page whose manifest declares its sections
(`labeled_sections`, `anchor_range`), from HTML read out of a JSON field, from a
page the recovery batch re-encodes before extracting, or from a body longer than
the 1,200 words the check reads. A dropped block's ordinal is used up, so later
blocks keep their paths.

The figure, sentence, declared-section and re-encoding conditions came from the
independent review of the first version (GPT-6.1 Sol, round 1), which built
pages it would still have emptied: a table whose linked column labels sit over
unlinked amounts ("Gross monthly income limit" over "$2,000"), two short
definitions written as link text ("Income means money received."), a WebWorks
page under `labeled_sections`, and a Windows-1252 page that
`recover_ingest_batch.py` decodes as UTF-8 before extracting, so the extractor
would read other link text than the check reads in the retained bytes. Each is
now a test. Among the flagged rows they keep no further content-labeled row, and
12 more navigation rows: Nebraska breadcrumbs whose section number is not linked,
and three menus whose labels end with a period. Round 2 (Opus 5.5, Subfleet's
fallback when no Codex lane was free) agreed and asked for table marks to count
as content too: a ✓ or ✗ cell under linked column labels now keeps its block,
and only `| / \ < > « » ‹ › • ·` may stand outside the links (round 3, also Opus
5.5, agreed and had hyphen and en-dash cells count as content too). On the flagged
rows the only such tokens in dropped blocks are three `|` and one `>`, so no
verdict changed.

One known loss remains by design. A list whose every item is a short linked
sentence without a final period ("Report changes within 10 days" over "Report
income over 130 percent of poverty") reads as a menu and is dropped, as are the
link lists counted below; the text such a link names lives on the page it links
to. Where that matters, `html_keep_navigation_blocks: true` keeps the list (a drop
selector cannot: it removes chrome, not the list), ideally with a drop selector for
the page's real chrome.

### How the conditions were chosen

The 1,198 flagged rows hold 602 distinct bodies. Each body was labeled twice by
GPT-6.1 Sol through Subfleet review lanes, with its headings, URL and the words
the navigation strings did not cover: once by a neutral classifier and once by
a reviewer told to defend the corpus text and to call anything uncertain
content. Labels: NAV (page or site furniture only), CONTENT (any of the
document's own substance, a status, a pointer that is the provision's
instruction, a definition, a figure) or MIXED. A body counts as content when
either review says CONTENT or MIXED. The reviews disagreed on 20 bodies; 495
bodies (1,066 rows) are navigation by both, 107 bodies (132 rows) content.

| Rule over the flagged rows | Rows dropped | Navigation by both reviews | Content by either |
| --- | ---: | ---: | ---: |
| The check's rule | 1,198 | 1,066 | 132 |
| Positional blocks only | 1,187 | 1,065 | 122 |
| … with no token of its own but link separators | 861 | 833 | 28 |
| … and at least two navigation strings | 448 | 435 | 13 |
| … and none longer than 12 words | 422 | 414 | 8 |
| … and none ending a sentence (`is_navigation_block`) | 419 | 411 | 8 |

All six rows were recomputed against `57cd05e01` from the 1,198 CSV-labeled
locked rows and their retained source bytes. The no-own-token row is corrected
from 863 / 835 / 28 to 861 / 833 / 28; the other five rows match the original
measurement. The final decisions also match every `extractor_drops` CSV label.

The cap trades a little either way. Capping at 6 or 8 words drops 6 content
rows instead of 8, but 92 or 49 fewer navigation rows: the strings of 9 to 12
words are mostly manual section and form titles in "Related Policy" and form
lists ("Parents and Caretaker Relatives Enter or Already Live in the Home,
A-846.1"), and the two extra content rows are link lists that the neutral review
calls navigation. Capping at 15 drops the same 8; at 20, 10. Letting a lone
string through when it occurs twice on its page is no safer: three content
singletons ("Appropriations", "Cash and Medical Decision Tree", an exhibit URL)
repeat on their pages, and about half the navigation singletons do not.

The eight content-labeled rows the extractor still drops are lists of links whose
link text names something: five "Prime Sponsors", "Senate" and "House" blocks
across three Colorado bill pages (legislators and committees), and three Washington HCA lists
(program application forms, two KDP manual editions with their effective dates,
and an index of participation references). None is statute, regulation or
manual text; each names other pages. Every row and both labels are in
[2026-10-13-html-navigation-blocks-review.csv](2026-10-13-html-navigation-blocks-review.csv).

## Measurement: re-extracting the 148 scopes

`scripts/measure_html_navigation_blocks.py` matches each retained HTML source to
its manifest entry (jurisdiction, class, file name, title, source URL and root
path, over every manifest in `manifests/` and the one the signed ingest command
names, as of the ingest commit) and extracts it twice from the locked bytes.

- **Reproduction.** With `html_keep_navigation_blocks: true` (the extractor
  before this change) 10,349 documents reproduce their locked rows byte for
  byte. One New Zealand document has drifted since its ingest and is left out;
  68 recovery documents (made by `scripts/recover_ingest_batch.py`) have no
  manifest entry; 1,149 sources are PDFs or come from other adapters. 129 of the
  148 scopes reproduce in full.
- **Successors.** With the filter, successors of the 130 scopes the extractor
  made drop **370 rows**. Every one is a row `is_navigation_block` flags on the
  locked rows, and every one is a `navigation_body` finding; no successor gains a
  new finding of any kind. `navigation_body` findings in the 148 scopes fall from
  1,198 to 828.
- **Paths.** Kept rows keep their citation path, ordinal, heading and body; only
  `block_count` changes. The original author reported that the 14 block rows of
  these scopes that `rulespec-us` and `rulespec-us-az` cite are unchanged in the
  successors; the nit-fix verification did not reproduce that cross-repository
  comparison.
- **The check.** `content-check --all --check-baseline` still passes over all
  2,390 locked scopes: the check's findings are unchanged.

### Why 828 flagged rows remain

| Kept because | Rows | Navigation by both reviews | Content by either |
| --- | ---: | ---: | ---: |
| One navigation string (a lone link, tab or control) | 391 | 376 | 15 |
| Words or figures of its own (a status, a pointer, a section code beside a link) | 289 | 199 | 90 |
| A string longer than 12 words | 24 | 19 | 5 |
| A string that ends a sentence | 1 | 1 | 0 |
| Declared section (Connecticut regulations) | 10 | 0 | 10 |
| Scope not made by the official-document extractor | 60 | 58 | 2 |
| Withdrawn July recovery scope | 53 | 51 | 2 |

The largest remainders are publisher-specific. Washington DSHS EA-Z pages carry
"Clarifying Information" and "Worker Responsibilities" tab links (179 of the
EA-Z manual's 187 remaining rows), and Texas handbooks list "Related Policy"
links whose section codes (A-1431, C-920) sit outside the links (225 rows). A
manifest drop selector for each publisher removes them without a general rule.

## Which scope families would gain from successor ingests

| Family | Scopes | `navigation_body` rows | A successor drops | Scopes that gain | Scopes left with none |
| --- | ---: | ---: | ---: | ---: | ---: |
| Wave 6 (2026-10-06) program-bundle scopes | 57 | 271 | 171 | 39 | 19 |
| State SNAP manuals and transmittals | 14 | 432 | 76 | 6 | 0 |
| State Medicaid and CHIP eligibility manuals (2026-09-10) | 9 | 230 | 72 | 2 | 0 |
| SSA POMS (SI, HI) | 3 | 49 | 15 | 2 | 0 |
| CMS state plans and SPAs | 18 | 41 | 13 | 10 | 8 |
| Program standards and federal notices (2026-09) | 14 | 24 | 11 | 8 | 4 |
| State TANF manuals | 3 | 8 | 1 | 1 | 0 |
| Other (BE, UK, NZ, NSF, MD, IL, AZ, CA) | 12 | 30 | 11 | 7 | 4 |
| Recovery scopes not withdrawn | 7 | 28 | 0 | 0 | 0 |
| Composed Canadian scopes | 3 | 32 | 0 | 0 | 0 |
| Withdrawn July recovery scopes | 8 | 53 | 0 | 0 | 0 |
| **Total** | **148** | **1,198** | **370** | **75** | **35** |

The scopes that gain most:

| Scope | Rows | A successor drops |
| --- | ---: | ---: |
| `us-tx/manual/2026-09-10-snap-state-manual-completion` | 163 | 43 |
| `us-tx/manual/2026-09-10-medicaid-state-eligibility-manual` | 145 | 37 |
| `us-wa/manual/2026-09-10-medicaid-state-eligibility-manual` | 66 | 35 |
| `us-il/guidance/2026-10-06-w6-health-guidance-il` | 18 | 18 |
| `us-mn/statute/2026-10-06-w6-tanf-ccdf-statutes-mn` | 22 | 17 |
| `us-va/guidance/2026-10-06-w6-tanf-ccdf-guidance-va` | 17 | 17 |
| `us-mn/regulation/2026-10-06-w6-tanf-ccdf-rules-mn` | 20 | 15 |
| `us-co/guidance/2026-10-06-w6-income-tax-guidance-co` | 21 | 14 |
| `us-pa/manual/2026-07-21-pa-snap-handbook` | 19 | 11 |

The wave 6 scopes gain most for least: 39 of 57 lose rows and 19 are left with
no `navigation_body` finding. The Texas and Washington manuals gain the most rows
but keep most of theirs until a publisher drop selector lands. The composed
Canadian scopes (14 rows the filter would drop) and the non-withdrawn recovery
scopes (up to 14; a recovery rerun keeps every block of a page it re-encodes)
gain only through re-composition or a recovery rerun; the withdrawn scopes need
no successor.

A successor is a separate signed ingest with its own run note, and selecting it
in place of a locked scope is a release decision. Re-fetching gives current
publisher text, which may differ from the locked bytes for reasons other than
this filter; extracting from the retained file (`local_path`) keeps the text but
records a `file://` download URL and no content type.

## Reproduce

```bash
uv run axiom-corpus-ingest corpus fetch <scope>...
uv run python scripts/measure_html_navigation_blocks.py --out <scratch dir> <scope>...
uv run axiom-corpus-ingest content-check --all --check-baseline --workers 4
```

The script writes each successor's rows to `<out>/provisions/<scope>.jsonl`, the
dropped rows to `<out>/dropped.jsonl` and per-scope counts to `<out>/summary.json`.

## Follow-ups

- Publisher drop selectors for the Washington DSHS EA-Z tab links and the Texas
  "Related Policy" lists (about 400 rows), in their manifests: declared as
  navigation in [2026-10-13-html-navigation-selectors.md](2026-10-13-html-navigation-selectors.md).
- `navigation_prefixed_body` (102 rows): bodies that open with chrome before
  their text. The filter does not trim prefixes.
- Successor ingests for the families above, beginning with the wave 6 scopes.
