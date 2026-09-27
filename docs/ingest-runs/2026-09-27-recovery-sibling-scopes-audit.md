# July recovery sibling scopes: audit and supersession

The us-ca statute recovery audit (#748, `2026-09-25-us-ca-statute-recovery-audit.md`,
follow-up 5) found the same family of defects in other scopes of the July US
source recovery. This run audits every row of the 18 scopes that sweep flagged,
finds where their text is carried faithfully, records what rulespec-us citations
resolve to, and decides for each scope whether to build a successor.

Every merged scope is unchanged. Nothing is fetched, published, loaded or
activated, and no tracked selector is added or edited.

## Decisions

| Scope | Rows | Rows without legal text | Where the text is carried | Successor | Next cut in a line that still selects it |
| --- | ---: | ---: | --- | --- | --- |
| `us-ny/statute/2026-07-13-recovery` | 11 | 0 (all 11 wrap the text in page chrome) | `us-ny/statute/2026-09-14-income-tax-chapter`: identical text, all 11 sections | no | drop it and the article 22 core scope; add the chapter scope |
| `us-id/statute/2026-07-13-recovery` | 15 | 15 | the 2026-07-31 chapter 30 successor and the wave4 chapter scope | no | none: no key line selects it |
| `us-me/statute/2026-07-13-recovery` | 13 | 12 | `us-me/statute/2026-09-14-income-tax-chapter-us-me-title-36` (all of §5111's table); that scope drops lettered paragraphs, which #754 restores | no | drop it; add the chapter scope, or #754's successor once merged |
| `us-mn/statute/2026-07-13-recovery` | 125 | 35 | `us-mn/statute/2026-09-14-income-tax-chapter-us-mn-title-290`: all 250 legal-text lines | no | drop it; add the three MN chapter scopes |
| `us-ut/statute/2026-07-13-recovery` | 3 | 0 (all 3 wrap the text in page chrome) | `us-ut/statute/2026-09-14-income-tax-chapter-title-59`: same words | no | drop it; add the chapter scope |
| `us-sc/statute/2026-07-13-recovery` | 3 | 3 | **nothing**: no scope carries §12-6-520 | **yes** | swap it for the successor |
| `us-mi/statute/2026-07-13-recovery` | 15 | 2 | `us-mi/statute/2026-09-14-income-tax-chapter-us-mi-chapter-206` | no | drop it; add the chapter scope |
| `us-mt/regulation/2026-07-13-recovery` | 1 | 0 (the rule wrapped in page chrome) | **nothing**: ARM 37.78.420 is only here | **yes** | swap it for the successor |
| `us-co/regulation/2026-07-13-recovery` | 192 | 4 | its own successor `…-r2026-09-11-tanf-consolidated`, which also replaces the wrong §3.606.x rows | no | swap it for the consolidated successor |
| `us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated` | 250 | 5 | (it is the carrier) | no | keep |
| `us-fl/regulation/2026-07-13-recovery`, `us-sc/regulation/…`, `us-tn/regulation/…` | 2, 3, 2 | all | the release scopes whose sources they re-fetched | no | drop them |
| `us-il/manual/2026-07-13-recovery-r2026-07-17-dedup` | 5 | 4 | the IL manual scope, byte for byte | no | drop it: that also repairs a cited path |
| `us-in/manual/…`, `us-sc/manual/…`, `us-ut/manual/…` | 2, 5, 7 | all | the release scopes whose sources they re-fetched | no | drop them |
| `us/guidance/2026-07-13-recovery` | 102 | 10 | ED FSA documents: nowhere else selected | no | keep |

The two successors are separate ingests, not part of this run (see
[Follow-ups](#follow-ups)). Swapping scopes in a tracked cut is a release decision
for Max; it is queued, not made here.

## How the rows were made

All 17 recovery scopes were added in ed8464a37 (2026-07-15) and merged by #344
(a9d5ec29f, 2026-07-16). The IL manual scope is the `-r2026-07-17-dedup`
re-version from bcf433c5a; the CO consolidated scope is the 2026-09-11
consolidation (3643139c7). `scripts/recover_ingest_batch.py` built the rows with
three functions:

- **`_targeted_state_html`** (`recover_ingest_batch.py:336-393`) stores the page's
  whole visible text, with only `script`, `style`, `nav`, `header` and `footer`
  removed, as one `section` row at the declared citation. That is every NY, UT
  and MT row and MI §206.272: site menus, breadcrumbs and "View historical
  revision" links come before the law, and reference lists, MAR notices and
  version lists after it.
- **`_generic`** (`:627-712`) runs the shared document extractor. For HTML,
  `documents._extract_html_blocks` (`src/axiom_corpus/corpus/documents.py:2818`)
  drops a fixed selector list, takes `_main_content` (the first `main`,
  `article`, `[role='main']`, `#main-content` or `.main-content`, else `body`;
  `:3566`), and reads only `h1`-`h6`, `p`, `li`, `table` and `blockquote` nodes
  (`_html_text_nodes`, `:3589`). A block is the run of nodes between headings.
  When the root holds no such node, the block is the root's whole text
  (`:2895-2906`). `_generic` puts a bodyless `document` root at the single
  declared citation, or at `recovery/<document id>` when it was not given exactly
  one.
- **`_materialize_planned_targets`** (`:802-866`) gives each planned citation the
  extractor did not emit a row by copying the whole body of the first row that
  prints the target's label (for `page-N` targets, the page of that number).

Replaying the first two on the retained bytes reproduces 38 documents' rows
exactly (`test_rows_are_what_the_recovery_builders_make_of_the_retained_bytes`).
In the four documents with alias copies, the copies differ from a replay only
in `parent_citation_path` and `parent_id`, which the committed rows leave null. Two documents (IL's CSMM page,
ED GEN-26-01) no longer pass `_generic`'s label check and are audited by content.

## Audit

```bash
uv run --extra dev python scripts/audit_recovery_sibling_scopes.py
```

The script writes
[`2026-09-27-recovery-sibling-scopes-audit.json`](2026-09-27-recovery-sibling-scopes-audit.json).
Its docstring defines each verdict. In short:

- A block row of an HTML page must equal, byte for byte, one block the shared
  extractor makes of the retained page. The verdict then follows from where that
  block's nodes sit relative to the site's legal-text container (NY
  `div.nys-openleg-result-text`, UT `div#secdiv`, MI `div.sectionWrapper`, ID
  `div.pgbrk`, ME `div.MRSSection`, MN `div#xtend` with its `div.history`, MT the
  react-pdf text layer). On the SC chapter page the "container" is the run
  between `SECTION` markers.
- A `_targeted_state_html` row is `page_text_with_chrome` only if it is exactly
  the page's flattened visible text and the container's text is a proper part
  of it.
- PDF rows must equal the shared PDF extractor's page (or, for the Colorado Works
  rows, the section of the same label made with the tracked manifest's
  `extraction` block).

All 756 rows get a verdict other than `unclassified`. Two tests check that the
verdicts are strict:

- `test_classifier_refuses_altered_rows`: dropping a block's first or last node,
  truncating, or changing one letter makes a row `unclassified`.
- `test_no_row_with_text_foreign_to_its_source_is_classified`, an invariant over
  every row of every scope: splicing a character that occurs in no row into a
  row's body, at its start, middle or end, makes it `unclassified`.

Every retained file hashes to the signed ingest manifest's `applied_files`
entry, and to its provenance sidecar where it has one. The only file without a
sidecar is the adapter-made Colorado Works PDF the consolidated scope carries.

| Scope | Rows | Files | Verdicts |
| --- | ---: | ---: | --- |
| us-ny statute | 11 | 11 | 11 `page_text_with_chrome` |
| us-id statute | 15 | 5 | 5 `empty_document_root`, 10 `site_chrome` |
| us-me statute | 13 | 6 | 6 `empty_document_root`, 6 `site_chrome`, 1 `legal_text` |
| us-mn statute | 125 | 5 | 5 `empty_document_root`, 30 `site_chrome`, 85 `legal_text`, 5 `history_note_and_site_chrome` |
| us-ut statute | 3 | 3 | 3 `page_text_with_chrome` |
| us-sc statute | 3 | 1 | 1 `empty_document_root`, 1 `site_chrome`, 1 `tables_from_other_sections` |
| us-mi statute | 15 | 3 | 2 `empty_document_root`, 2 `legal_text`, 1 `page_text_with_chrome`, 10 `alias_copy` |
| us-mt regulation | 1 | 1 | 1 `page_text_with_chrome` |
| us-co regulation (recovery) | 192 | 3 | 3 `empty_document_root`, 1 `landing_page_text`, 185 `document_page_text`, 3 `alias_copy` |
| us-co regulation (consolidated) | 250 | 4 | 4 `empty_document_root`, 1 `landing_page_text`, 185 `document_page_text`, 60 `document_section_text` |
| us-fl, us-sc, us-tn regulation | 2, 3, 2 | 1 each | one `empty_document_root` each; the rest `landing_page_text` |
| us-il manual | 5 | 2 | 1 `empty_document_root`, 3 `landing_page_text`, 1 `document_page_text` |
| us-in, us-sc, us-ut manual | 2, 5, 7 | 1 each | one `empty_document_root` each; the rest `landing_page_text` |
| us guidance | 102 | 7 | 7 `empty_document_root`, 3 `landing_page_text`, 89 `document_page_text`, 3 `alias_copy` |

## Findings by scope

**New York.** Each of the 11 rows is the nysenate.gov page from "NYS Open
Legislation | NYSenate.gov Sorry, you need to enable JavaScript…" through the
navigation to "§ 673. Credit for tax withheld…". The container text equals,
word for word, the section text of the wave4 chapter scope (whose roots compose
from one child block) and of its `-r2026-09-23-line-structure` successor.

**Idaho.** Each page prints the section inside `div.pgbrk` as `span`s, which the
block extractor never reads, so each document is an empty root, the legislature
menu and "How current is this law?". Every word of both carriers' section text
occurs in the container. The pages for §§63-3022E and 63-3025D print two versions
("effective until January 1, 2027" and "effective January 1, 2027"); both
carriers hold only the first.

**Maine.** `block-1` of each document is the left-hand "§… PDF / MS-Word /
Statute Search / … Contents" list. The section text sits in `div`s the extractor
does not read, except §5111's rate table, which is `block-2`. All 18 of its lines
occur in the chapter scope. Every word of the chapter scope's text occurs on the
retained pages, but the pages have 138 to 927 more words per section: headings,
history brackets, and the lettered paragraphs the chapter scope drops (#754).

**Minnesota.** Per section: six chrome blocks (the header, "Authenticate / PDF",
search links, "Table of Sections / Full Chapter Text / Version List", the
"Version List" heading and the list itself), the subdivision text, and a last block with the history note (for §290.06
also a revisor's effective-date note) and the "Official Publication" footer. All
250 legal-text lines occur in the chapter scope.

**Utah.** Each row runs from "Utah Code Section 59-10-104 Home Utah Code Title 59
…" to the history line. Setting parenthesized markers aside (the chapter scope
prints `(2)(a)`), every word of the chapter scope's text is on the page; the page
adds 19 words each (heading, effective date, history), which the chapter scope
keeps in metadata.

**South Carolina statute.** The retained page is the whole of Chapter 6
(`t12c006.php`). `block-1` is the legislature menu; `block-2` is every `table` of
the chapter, printed under §§12-6-510, 12-6-545, 12-6-3535 and 12-6-3910, and none
from §12-6-520. The section's own text is in the page, outside any node the
extractor reads. `2026-07-16-pit-central-us-sc-title-12-chapter-6` carried
`us-sc/statute/12-6-520` as extracted (bb44b3e53). The next day "Deduplicate PIT
release citations" (fbc9f07da) removed that row in favour of this scope's empty
root, and the Act 110 overlay (`2026-07-24-sc-act110-…`) was built without it. No
scope on `main` carries §12-6-520's text. The SC adapter's own parser
(`parse_south_carolina_chapter_html`) reads it from this scope's retained page,
which is byte for byte the chapter page the pit-central and Act 110 scopes
retain. The section it reads equals the removed row's heading and body.

**Michigan.** §206.272's row is the whole MCL page. The §206.30 and §206.51 pages
became an empty `recovery/us-mi-code-*` root and one block holding the whole
section. The ten cited subsection paths (`206.30/2`, …, `206.51/10`) are
`alias_copy` rows: each is the whole section (43,548 or 11,767 characters).

**Montana.** The row is the rules.mt.gov page: title, "Montana SOS Skip to main
content Back View in PDF NEW", the rule twice-headed, the text, then history,
MAR notices, references, "Referenced by" and the version list. No other scope
carries the rule.

**Colorado.** The landing document is the Secretary of State's CCR welcome page.
The 8 CCR 1403-1 PDF became a bodyless root at `8-ccr-1403-1/3.111` over all 75
pages. The three 9 CCR 2503-6 targets are page copies: §3.606.1 copies page 110,
the rule's amendment history; §3.606.2 copies page 53, which does not open with
the section; §3.606.6 copies page 61, which does. The consolidated successor
keeps 189 rows with the same text and replaces the three copies with the sections of
the Colorado Works PDF (`document_section_text`).

**Landing scopes.** Each re-fetched the source of an earlier release scope and
got an index or welcome page: flrules.org's "Div. 64V: Vital Statistics", the SC
Code of Regulations master list, TN rule chapter 1240's index, the IDHS policy
manual table of contents, the IN FSSA policy manual page, the SC DSS manuals
page and the UT DWS manual welcome page. The scope each one names still carries
the document's rows, and every key line selects it. The IL scope's one text row,
`dhs/csmm/19812/block-2`, is byte for byte the IL manual scope's
`dhs/csmm/19812/block-1`.

**Federal guidance.** The three FNS pages are landing pages: their `main` holds
only the title and "Page updated", which became the block through the
extractor's fallback. The memos are PDFs that the named release scopes carry.
Rev. Proc. 2025-25's rows equal those of `2026-06-01-irs-rev-proc-2025-25-…`,
which no key line selects. Rev. Proc. 2025-32's and the ED FSA documents' rows
are the shared extractor's pages and blocks of those documents.

## What resolves against these rows downstream

axiom-encode resolves a citation in `corpus_resolver.resolve_local_corpus_source`
(read at 06b01708):

- The exact path comes first (`_citation_lookup_groups`).
- Ancestors are tried only when no exact row exists, and only for `statute`,
  `regulation` and `legislation` paths of four or more segments
  (`_parent_citation_paths`). A `manual` or `guidance` path never falls back.
- A body that is empty or whitespace counts as null (`_record_body`). Such a
  row's body is composed from its descendants, which must all be in the same
  scope; otherwise resolution fails with "Corpus descendants … cross active
  release scopes" (`_compose_descendant_text`).
- An ancestor hit is sliced to the requested fragment (`_slice_parent_body`).

```bash
<axiom-encode>/.venv/bin/python scripts/resolve_recovery_sibling_citations.py \
  --encode-src <axiom-encode>/src --encode-rev 06b017082645f2af0504d2a93e4ffd64c45d4c52 \
  --rulespec-index <rulespec-us>/.axiom/index/provisions_to_rules.json \
  --rulespec-rev dcb2e47e0af964be6d59f80688f519d0a6a96a71
```

It runs that resolver over every path rulespec-us cites under each scope's
jurisdiction and class, for every key line that selects the scope, as selected
and with the swap above. The only step it skips is the check of the release
object's signature. Output:
[`2026-09-27-recovery-sibling-scopes-downstream.json`](2026-09-27-recovery-sibling-scopes-downstream.json).
Under the live pin (`us-rulespec-2026-08-08-obbb-alien-snap`):

- **NY, UT, MT, MI §206.272.** Modules get the section text with the page chrome
  around it.
- **ME.** Five of six cited roots (`36/5124-C`, `5126-A`, `5213-A`, `5219-S`,
  `5219-SS`, two modules each) compose to the menu block alone, 199 to 235
  characters. `36/5111` composes to menu plus table.
- **MN.** Roots compose to chrome, text and history, menus first.
- **MI subsections.** Each gets the whole section.
- **SC.** `us-sc/statutes/12-6-520.yaml` gets the menu plus the tables of four
  other sections.
- **CO.** Eight modules citing `9-ccr-2503-6/3.606.1` get the amendment-history
  page. `8-ccr-1403-1/3.111` gets the whole 222,420-character rulebook.
- **IL.** `us-il/manual/dhs/csmm/19812` does not resolve in any key line: the
  dedup scope's `block-2` sits under the manual scope's bodyless root, so the
  composition crosses scopes.

After the swap:

- NY, UT, MN, ME and MI roots resolve to the chapter scopes, and the MI
  subsection paths to ancestor slices of real subsection text.
- CO's §3.606.x paths get the Colorado Works sections.
- IL `19812` resolves to the manual scope's block.
- Four statute citations fail. `us-me/statute/36/5111/block-2` and
  `us-mn/statute/290.06/block-12`, `-13` cannot be sliced from the chapter rows;
  the wave4 consolidation already lists them as dangling, and draft
  rulespec-us#1365 re-points the citations that consolidation dropped. `us-sc/statute/12-6-520` is not found, which is why SC needs a
  successor before it can leave.
- Dropping MT leaves its rule unfound for the same reason.
- Dropping `us/guidance/2026-07-13-recovery` would leave five cited ED and IRS
  paths unfound in every line, so it stays.

## Selectors

| Scope | Tracked selectors | obbb | snap-fy2027 | canada-338 | wave4 | wave4-r2 |
| --- | ---: | :-: | :-: | :-: | :-: | :-: |
| us-ny statute | 11 | yes | yes | yes | no | no |
| us-id statute | 22 | no | no | no | no | no |
| us-me, us-mn, us-ut, us-mi statute | 32 each | yes | yes | yes | no | no |
| us-co regulation (recovery) | 28 | yes | yes | yes | no | no |
| us-co regulation (consolidated) | 6 | no | no | no | yes | yes |
| us-sc statute, us-mt regulation, and the eight landing, IL and guidance scopes | 34 each | yes | yes | yes | yes | yes |

Every row of this table is in the audit JSON (`selectors`). rulespec-us pins the
obbb line; #747 cut its successor, snap-fy2027; rulespec-us#1389 stages a re-pin
to canada-338. For every statute scope and the CO recovery scope, the swap above
is what the wave4 line already did
(`test_the_proposed_swap_validates_on_the_obbb_line` also checks that applying it
to the obbb line's scopes of the pair passes `validate_release` with strict
warnings and no issue).

**Activation.** `corpus.activate_corpus_release` upserts
`corpus.active_scope_pointer` for each `(jurisdiction, document_class)` pair the
release carries
(`supabase/migrations/20260719043000_profiled_release_activation.sql:255-300`).
A cut that keeps a pair, without the dropped scope, therefore takes that scope
out of serving for the pair. Activating an older release that still selects it
puts it back.

**The release gate does not see these defects.** `validate_release` passes every
audited scope alone with strict warnings and no issue
(`test_release_validation_does_not_see_the_defects`).

This run adds no selector-freeze guard like the CA audit's: which lines take
these swaps, and when, is queued for Max.

## Follow-ups

1. **SC successor.** A signed scope carrying `us-sc/statute/12-6-520` extracted by
   the SC adapter from the retained chapter page, and the Act 110 overlay applied
   to it if Act 110 touches it. Then swap it in for this scope in every line.
2. **MT successor.** ARM 37.78.420 without the page chrome, from the retained page
   or the rule's PDF.
3. **CO 8 CCR 1403-1.** Split the rulebook into sections so `3.111` resolves to
   §3.111, not to all 75 pages.
4. **ID concurrent versions.** Both ID chapter carriers hold only the version of
   §§63-3022E and 63-3025D in force until 2027-01-01; the retained pages print
   the version effective that day too (compare #752 for CA and #754 for ME).
5. **rulespec-us.** The CO §3.606.1 modules (eight), the ME modules citing
   chrome-only roots, `us-sc/statutes/12-6-520.yaml` and the IL `19812` citation
   resolve to no legal text today. Record or repair them on the rulespec-us side.
6. **Release gate.** The CA audit's follow-up 3 (a content check for chrome,
   empty roots at section paths and landing pages, and a withdrawn-scope list)
   would catch every defect here.

## Checks

Run on `origin/main` f1916d73b with this branch's files, in a sparse checkout
that has every audited scope's sources and the sources of the scopes each swap
test validates:

- `uv run --extra dev python -m pytest -q tests/test_recovery_sibling_scopes_audit.py`:
  64 passed.
- The audit command above rewrote the committed JSON byte-identically.
- `uv run --extra dev ruff check` and `ruff format --check` on the new scripts and
  test: passed.
- The downstream JSON was generated with the command above.
- `towncrier check --compare-with origin/main` finds the fragment.
- No protected corpus artifact or ingest manifest is touched, so there is nothing
  to sign.
