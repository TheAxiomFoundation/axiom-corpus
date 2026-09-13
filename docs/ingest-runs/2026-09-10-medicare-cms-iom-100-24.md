# Medicare: CMS Internet-Only Manual Pub 100-24 (State Payment of Medicare Premiums)

Date: 2026-09-10 (version date; the run finished 2026-09-11)
Program: Medicare (board Year 1 list; `manifests/medicare-agent-queue.yaml`)
Agent: started_at 2026-09-11T11:37:14+0200, finished_at 2026-09-11T11:46:34+0200, wall time 9 min 20 s. Two earlier agents on this
branch were stopped before writing a note; they left the generator extension, the manifest and the queue
row (file mtimes 2026-09-11T01:10:58+0200, chapter PDFs cached 00:58) and a first extraction into the corpus
base (artifacts 01:08-01:11). This run verified that state, re-ran the extraction (artifacts below supersede
the earlier ones at the same paths) and wrote this note.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing library
function was modified: the only code change extends `scripts/build_cms_iom_100_01_manifests.py`
(a `--publication` switch; the Pub 100-01 path is unchanged and `manifests/us-cms-iom-100-01.yaml` is
byte-identical).

Source: CMS Internet-Only Manuals (IOM) index,
https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms
(Centers for Medicare & Medicaid Services), confirmed live on 2026-09-11 (25 publications). Its Pub 100-24
page (https://www.cms.gov/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms019212)
lists six "Chapter N - Title" PDFs and one "100-24 Table of Contents" PDF. Chapters 1, 2, 4 and 6 are served
from `/files/document/chapter-N-<slug>.pdf`, chapters 3 and 5 from
`/regulations-and-guidance/guidance/manuals/downloads/buyin_c0N.pdf`; the manifest URLs equal the page's
hrefs. Family: CMS manuals (second publication after Pub 100-01, see
`docs/ingest-runs/2026-09-10-medicare-cms-iom-100-01.md`).

Scope: 1 jurisdiction (`us`), document_class `manual`, version
`2026-09-10-medicare-cms-iom-100-24`, 6 documents (chapters 1-6), citation path
`us/manual/cms/iom/100-24/chapter-<n>/<section label>` (for example `.../chapter-1/1.6.2.4`,
`.../chapter-5/5.A`). `--source-as-of 2026-09-10`; `expression_date` per chapter = the issued date of the
latest transmittal printed in the chapter's table-of-contents header, as in the 100-01 run:
ch. 1 2025-01-16 ("(Rev. 7; Issued: 01-16-2025)"), ch. 2-6 2020-08-21 ("(Rev. 4, 08-21-20)"; ch. 6 prints
"(Rev.4, 08-21-20)"). Each header prints exactly one transmittal. HTTP Last-Modified was sent for every
chapter and is recorded in metadata (ch. 1 2025-01-17, ch. 2-6 2020-09-03).

## Index inventory

IOM index: 25 publications found, 2 taken (100-01 earlier, 100-24 now). Chapter counts are the
"Chapter N - Title" download links on each publication page; "other" counts the page's remaining downloads.
The counts were re-read live by the generator on 2026-09-11 and match the 100-01 note's table, so only the
100-24 row changed:

| Pub | Title | Chapters | Other | Taken |
|---|---|---|---|---|
| 100-01 | Medicare General Information, Eligibility and Entitlement Manual | 7 | 1 (Crosswalks) | yes (2026-09-10-medicare-cms-iom-100-01) |
| 100-24 | State Payment of Medicare Premiums | 6 | 1 (100-24 Table of Contents) | yes, all 6 chapters |
| 100, 100-17 to 100-21, 100-25 | whole-manual download only (no chapter links) | 0 | 1-2 each | no |
| 100-12, 100-13, 100-23 | under development, no documents | 0 | 0 | no |
| 100-02, 100-04 | Benefit Policy (17), Claims Processing (41) | | | no, candidate later families |
| 100-03, 100-05 to 100-11, 100-15, 100-16, 100-22 | other IOM families | 3-17 each | | no |

The full per-publication rows (URLs, chapter counts, other documents) are in the queue row under
`index_inventory`; `index_families` summarises each publication's status (taken / candidate_later_family /
not_taken / whole_manual_download_only / no_documents); `publications` carries the Pub 100-24 entry
(document_count 7, chapter_count 6, chapters_taken 6, not_taken ["100-24 Table of Contents"]). The Pub
100-01 family is still described by the row's singular keys (`target_manifest`, `publication_page`).
`paper_based_manuals` is unchanged (Pub 15-1, 15-2, 45; none taken).

Pub 100-24 page: 7 documents, 6 chapters taken, 1 not taken (the Table of Contents PDF is a finding aid that
repeats the chapter TOCs already present in each chapter PDF).

Blocked: nothing. cms.gov served the index, the publication page and every chapter PDF (HTTP 200) to the
corpus user agent with plain `requests` + certifi. No TLS bundle, `data/certs` change or
`browser_impersonation` was needed; TLS verification stayed on.

## Extraction

`labeled_sections` with `section_heading_requires_bold: true`, as for Pub 100-01, but the heading shape
differs, so the generator carries a per-publication pattern. Pub 100-24 prints dotted chapter.section labels
with an optional dash: "1.1 Definitions" (ch. 1), "2.2 - Frequency of ...", "2.2.1- State Input Files"
(ch. 2-6), and bold "Appendix 5.A - Medicare Part A Premium Amount" appendices with their own transmittal
lines. Heading pattern
`^(?:Appendix\s+)?(?P<label>\d+\.(?:\d+(?:\.\d+)*|[A-Z]))(?:\s+|\s*[-–—]\s*)(?P<heading>[A-Z(].*)$`:
the label must contain a dot (so "1-800" text never matches) and the heading must start with an upper-case
letter or "(" so bold wrapped cross-references ("1.7 and 1.11 for more information ...", "00805.385 at
https://...") are not headings. Appendices are emitted as sections labeled by the printed code (1.A-1.D,
5.A-5.D, 6.A-6.B). The table of contents is dropped with a per-chapter `start_after_pattern` on the
chapter's last TOC line, computed by the generator (ch. 1 "Specified U.S. Territories", ch. 2
"2.11.2 Medicare Part A", ch. 3 "3.5.10 CMS/TPS Buy-in Exchange Trailer Record", ch. 4 "4.8.2 SSI Status
Codes - Deletion", ch. 5 "Appendix 5.D Listed Agency Billing (LAB) - Summary Sheet", ch. 6 "Appendix 6.B RRB
Report of State Buy-in Problem (Form RL-380F)"). Wrapped headings are joined with the 100-01
`heading_continuation_pattern`, in a variant whose all-caps guard rejects two or more capitals
(`(?![A-Z]{2,}:?$)`) instead of one or more, because ch. 2 §2.6.2.6 "Beneficiary Becomes Entitled to
Reduced or Premium-Free Part" wraps onto a bare "A" line; bold captions ("POLICY", "NOTE") are still
rejected and the transmittal line stays as the first body line.

Heading pattern proof, TOC section count (labels matched in the TOC, before the start_after line) against
emitted sections, checked on the chapter PDFs and the provisions JSONL:

| Chapter | Title | Pages | TOC sections | Emitted | Mismatch |
|---|---|---|---|---|---|
| 1 | Program Overview and Policy | 63 | 54 | 55 | body §1.6 "Part B Buy-in Coverage Groups in the 50 States and the District of Columbia - General" has no parseable TOC entry: the TOC text layer prints it interleaved with the §1.6.1 line ("1.6.1 Cash 1.6 Buy-in Coverage Group One: ..."); the body governs |
| 2 | Data Exchange Processes | 37 | 61 | 61 | none |
| 3 | Data Exchange | 56 | 20 | 20 | none |
| 4 | Code Descriptions | 41 | 17 | 17 | none |
| 5 | Premium Billing | 17 | 17 | 17 | none (13 numbered + 4 appendices) |
| 6 | Problem Cases and Resources | 15 | 24 | 24 | none (22 numbered + 2 appendices) |

Every TOC label is emitted, no label is emitted twice, every section has a body and every body starts with
its transmittal line (194 of 194). Emitted heading text was compared to the TOC entry of the same label:
apart from dash style (the ch. 1 TOC prints "1.4.1 – General Requirements" where the body prints "1.4.1
General Requirements") the TOC wording differs from the body heading in eight places, all source
discrepancies where the body governs: ch. 1 §1.3.6 (TOC "Part A and B"), §1.4.3 ("States Liability"),
§1.4.4 (TOC "Medicare Eligibility Redeterminations", body "Medicaid ..."), §1.6.2.8 ("Qualifying
Individual"), §1.11 (TOC adds "Group"), §1.15 (TOC "Implications and Options"), §1.7 (TOC line wraps);
ch. 3 §3.3.2 (TOC "State Agency Buy-in ..."). Chapters 4-6 match exactly.

Smoke runs (scratch base, `--only-source-id`, `--allow-incomplete`, each downloading its PDF):
ch. 1 56 provisions 15.3 s, ch. 2 62 provisions 5.4 s, ch. 3 21 provisions 4.8 s, ch. 4 18 provisions 4.6 s,
ch. 5 18 provisions 4.2 s, ch. 6 25 provisions 4.8 s; each coverage complete.

Full run 2026-09-11 11:42:16-11:42:31+0200 (14.6 s wall, `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`):
200 provisions written, then an explicit `coverage --write` recompute agreed.

Counts: 1 scope, 6 documents, 200 provisions = 6 chapter roots + 194 sections
(ch. 1 55, ch. 2 61, ch. 3 20, ch. 4 17, ch. 5 17, ch. 6 24). Coverage `complete: true`, 0 missing,
0 extra, 0 duplicate citation paths (also checked directly on the provisions JSONL: 200 unique). No
citation path collides with any other provisions JSONL under `data/corpus/provisions/us/` (240 files
scanned, 0 collisions, none skipped). Source PDFs 2,790,516 bytes; SHA-256 of every file matches the
inventory.

Artifacts (unsigned, awaiting controller):

- `data/corpus/sources/us/manual/2026-09-10-medicare-cms-iom-100-24/official-documents/us-cms-iom-100-24-chapter-<n>.pdf` (n = 1..6)
- `data/corpus/inventory/us/manual/2026-09-10-medicare-cms-iom-100-24.json`
- `data/corpus/provisions/us/manual/2026-09-10-medicare-cms-iom-100-24.jsonl`
- `data/corpus/coverage/us/manual/2026-09-10-medicare-cms-iom-100-24.json`

Rebuild:

```bash
uv run python scripts/build_cms_iom_100_01_manifests.py --publication 100-24   # reads the IOM index, writes the manifest and queue
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-medicare-cms-iom-100-24 --manifest manifests/us-cms-iom-100-24.yaml \
  --source-as-of 2026-09-10
```

Tests: `uv run ruff check scripts/build_cms_iom_100_01_manifests.py` clean; `ruff check scripts/` also reports 8
pre-existing findings in `scripts/build_liheap_state_plan_manifests.py` and `scripts/draft_program_work_orders.py`
(earlier commits on this branch, not touched here).
`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
→ 255 passed, 2 skipped, 10 failed. The 10 failures are the known sparse-worktree `FileNotFoundError`
cases on retained `data/corpus/...` artifacts (test_be_rulespec_2026_08_23_promotion,
test_build_ny_tanf_compatibility_scope ×2, test_rulespec_be_source_promotion, test_us_ak/ct/mi/mt/nd/ny
SNAP manual tests), identical to the 100-01 run; none touch the official-documents extractor or the files
in this commit.

## Reviewer judgments

1. Section paths are flat under the chapter (`chapter-1/1.6.2.4`, all level 2), as for Pub 100-01;
   the label carries the hierarchy. Appendices sit beside the numbered sections under their printed code
   (`chapter-5/5.A`).
2. The emitted heading is "label heading" as the extractor composes it: the dash the body prints in
   chapters 2-6 ("2.2 - Frequency ...") and the en dashes in the ch. 1 TOC are not part of the heading
   text. Wrapped heading lines are joined with a space, so ch. 1 §1.6.2.3 reads "... Part D Low- Income
   Subsidy (LIS) Leads Data" (the body wraps at the hyphen) and ch. 2 §2.4.1.4 ends "File Exchange3" (a
   footnote marker glued to the word in the PDF text layer). Both are kept as source text.
3. The bold transmittal line under each heading is kept as the first line of the body (source text,
   section-level provenance). Unlike Pub 100-01, every section here has one and none is empty.
4. Chapter 1's TOC parses to 54 labels against 55 body sections because the TOC text layer garbles the
   §1.6 entry (see the table); the body governs, so §1.6 is emitted. The eight TOC-vs-body wording
   differences listed above are source discrepancies; headings follow the body.
5. `expression_date` = latest TOC transmittal issued date per chapter (2025-01-16 for ch. 1, 2020-08-21
   for ch. 2-6). If the release wants one date per scope, rerun with `--expression-date 2026-09-10`
   after removing the per-document values (same option as 100-01 judgment 5).
6. The "100-24 Table of Contents" PDF on the publication page is a finding aid and is not taken.
7. The generator now takes `--publication`; adding a publication means adding a `Publication` record
   (version, heading pattern, continuation variant, queue note). The 100-01 heading pattern was not reused
   because Pub 100-24 prints labels without a spaced dash in ch. 1 and with "N.N.N-" in ch. 2-6; each
   IOM still has to be proven separately.
8. Queue shape: rather than a second state row for the same jurisdiction, the federal row is extended
   (`taken_count 2`, `publications`, `index_families`, `index_inventory[100-24].taken: true`, note
   appended). The singular keys still describe Pub 100-01, the first family; a later cleanup could move
   100-01 into `publications` too. `status_counts` recomputed (`agent_ready: 1`, one row).
9. Remaining IOM families (not taken): Pub 100-02 Medicare Benefit Policy Manual (17 chapters) and Pub
   100-04 Medicare Claims Processing Manual (41 chapters) as candidate later families; Pub 100-03, 100-05
   to 100-11, 100-15, 100-16, 100-22 have chapter PDFs but are outside the Medicare eligibility/premium
   scope; Pub 100, 100-17 to 100-21 and 100-25 are whole-manual downloads only; 100-12, 100-13 and 100-23
   have no documents. Paper-based Pub 45 State Medicaid Manual (ZIP chapters) still needs an adapter or
   pre-unpack step.

Remaining (controller): `sign-ingest-manifest` for the scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2); nothing here was pushed, signed, published or
loaded.
