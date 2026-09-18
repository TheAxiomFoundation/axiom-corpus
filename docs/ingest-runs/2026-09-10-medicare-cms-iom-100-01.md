# Medicare: CMS Internet-Only Manual Pub 100-01 (General Information, Eligibility, and Entitlement)

Date: 2026-09-10
Program: Medicare (board Year 1 list; `manifests/medicare-agent-queue.yaml`)
Agent: started_at 2026-09-10T16:33:32+0200, finished_at 2026-09-10T16:52:38+0200, wall time 19 min 6 s.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No existing
function was modified: the only code added is `scripts/build_cms_iom_100_01_manifests.py`.

Source: CMS Internet-Only Manuals (IOM) index,
https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms
(Centers for Medicare & Medicaid Services), confirmed live. It lists one page per publication;
the Pub 100-01 page (https://www.cms.gov/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms050111)
lists one PDF per chapter under `/regulations-and-guidance/guidance/manuals/downloads/ge101c0N.pdf`
plus a Crosswalks PDF. Family: CMS manuals. The lead list's cms.gov premium/deductible fact
sheets, medicare.gov pages, SSA POMS SI 01715.010, the SMD letter smd10003.pdf, and the Maine,
Massachusetts and Missouri state pages are not CMS manuals and are left out of this family
(see judgments below); law.cornell.edu mirrors stay excluded.

Scope: 1 jurisdiction (`us`), document_class `manual`, version
`2026-09-10-medicare-cms-iom-100-01`, 7 documents (chapters 1-7), citation path
`us/manual/cms/iom/100-01/chapter-<n>/<section label>` (for example `.../chapter-3/10.1`).
`--source-as-of 2026-09-10`; `expression_date` per chapter = the issued date of the latest
transmittal printed in the chapter's table-of-contents header ("(Rev. 12425; Issued: 12-21-23)"):
ch. 1 2023-12-21 (Rev. 12425), ch. 2 2023-05-18 (Rev. 12046), ch. 3 2024-11-25 (Rev. 12980),
ch. 4 2023-12-21 (Rev. 12425), ch. 5 2023-12-21 (Rev. 12425), ch. 6 2019-05-17 (Rev. 124; the
header prints Rev. 123 and Rev. 124, the later one is used), ch. 7 2025-04-17 (Rev. 13175).
HTTP Last-Modified is recorded in metadata where the server sent one (all chapters except [6]).

## Index inventory

IOM index: 25 publications found, 1 taken. Chapter counts are the "Chapter N - Title" download
links on each publication page; "other" counts the page's remaining downloads (crosswalks,
appendices, whole-manual PDFs/ZIPs). The site-wide "Marketplace help desk" footer link is ignored.

| Pub | Title | Chapters | Other | Taken |
|---|---|---|---|---|
| 100 | Introduction | 0 | 1 (Pub 100 - Introduction PDF) | no |
| 100-01 | Medicare General Information, Eligibility and Entitlement Manual | 7 | 1 (Crosswalks) | yes, all 7 chapters |
| 100-02 | Medicare Benefit Policy Manual | 17 | 16 per-chapter crosswalks | no |
| 100-03 | Medicare National Coverage Determinations (NCD) Manual | 4 | 2 crosswalks | no |
| 100-04 | Medicare Claims Processing Manual | 41 | 29 per-chapter crosswalks | no |
| 100-05 | Medicare Secondary Payer Manual | 8 | 8 (ch. 5.x user guides) | no |
| 100-06 | Medicare Financial Management Manual | 11 | 0 | no |
| 100-07 | State Operations Manual | 10 | 1 (SOM Appendix) | no |
| 100-08 | Medicare Program Integrity Manual | 15 | 3 (ch. 15.x processing guides) | no |
| 100-09 | Medicare Contractor Beneficiary and Provider Communications Manual | 5 | 1 (Crosswalk) | no |
| 100-10 | Quality Improvement Organization Manual | 12 | 0 | no |
| 100-11 | Programs of All-Inclusive Care for the Elderly (PACE) Manual | 17 | 2 (TOC, Glossary) | no |
| 100-12 | State Medicaid Manual (new manual under development; page has no documents) | 0 | 0 | no |
| 100-13 | Medicaid State Childrens Health Insurance Program (under development) | 0 | 0 | no |
| 100-15 | Medicaid Program Integrity Manual | 5 | 1 (Appendices) | no |
| 100-16 | Medicare Managed Care Manual | 15 | 10 (subchapters, appendices) | no |
| 100-17 | CMS/Business Partners Systems Security Manual | 0 | 2 (whole-manual PDFs) | no |
| 100-18 | Medicare Prescription Drug Benefit Manual | 0 | 1 (whole-manual PDF) | no |
| 100-19 | Demonstrations | 0 | 1 | no |
| 100-20 | One-Time Notification | 0 | 1 | no |
| 100-21 | Reserved | 0 | 1 | no |
| 100-22 | Medicare Quality Reporting Incentive Programs Manual | 3 | 0 | no |
| 100-23 | Payment Error Rate Measurement (under development) | 0 | 0 | no |
| 100-24 | State Payment of Medicare Premiums | 6 | 1 (TOC) | no |
| 100-25 | Information Security Acceptable Risk Safeguards Manual | 0 | 1 (ZIP) | no |

There is no Pub 100-14 on the index. The index also links the Paper-Based Manuals page
(https://www.cms.gov/medicare/regulations-guidance/manuals/paper-based-manuals): Pub 15-1
Provider Reimbursement Manual Part 1 (26 chapters), Pub 15-2 Part 2 (37 chapters), Pub 45 State
Medicaid Manual (12 chapter ZIPs: 1-9, 11, 13, 15); none taken. The full per-publication
inventory (URLs, chapter counts, other documents) is in the queue row under `index_inventory`
and `paper_based_manuals`.

Blocked: nothing. cms.gov served the index, every publication page and every chapter PDF
(HTTP 200) to the corpus user agent with plain `requests` + certifi. No TLS bundle,
`data/certs` change, or `browser_impersonation` was needed.

## Extraction

`labeled_sections`. Heading pattern `^(?P<label>\d+(?:\.\d+)*)\s+[-–—]\s*(?P<heading>[A-Za-z(].*)$`
with `section_heading_requires_bold: true`: every section heading in the body is bold, while
the false matches (`10-foot`, `1-800-MEDICARE`, `1966 – 1972`, `100-01 - General Information`
references, and a non-bold `40.2 – Shared System Maintainer` table cell in ch. 7) are either
excluded by the spaced dash or not bold. The table of contents (which repeats every heading)
is dropped with a per-chapter `start_after_pattern` anchored on the chapter's last TOC line,
computed by the generator from the PDF (the body starts where the first TOC label reappears).
Wrapped headings are joined with a `heading_continuation_pattern` that accepts Title-Case
continuation lines ("Payer (D-SEP)", "or After October 1, 1983 Under PPS", "Services – General")
and rejects the bold transmittal line that follows every heading ("(Rev. 1, 09-11-02)",
"(Rev .11764; ...)", "(Rev.: 128, ...)"), bold sub-captions ("A. General", "NOTE:", "POLICY"),
and anything shaped like the next section heading. The transmittal line therefore stays as the
first line of each section body. Verified against the bold headings of all seven PDFs: 334
sections, every heading identical to the source heading text, no duplicates.

Smoke runs (scratch base, `--only-source-id`): chapter 2 (68 provisions) and chapter 3
(29 provisions), each 1 s, coverage complete, before the full run. Both were re-run after the
continuation-pattern fixes described below.

Full run history (each 4 s, `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`):
16:45:07-16:45:11+0200 first run, 341 provisions, complete; the continuation pattern was then
widened to accept a bare dash token so two wrapped headings (ch. 1 §10.1, ch. 4 §10) keep their
second line; 16:48:49-16:48:53 second run regressed to 340 because ch. 3 §10 (a bare container
heading with no transmittal line) absorbed the following "10.1 - ..." heading; the pattern was
given a negative lookahead for heading-shaped lines; 16:49:35-16:49:39 final run, 341
provisions, and an explicit `coverage --write` recompute agreed. The final artifacts supersede
the earlier runs (same paths).

Counts: 1 scope, 7 documents, 341 provisions = 7 chapter roots + 334 sections
(ch. 1 30, ch. 2 67, ch. 3 28, ch. 4 31, ch. 5 60, ch. 6 60, ch. 7 58). Coverage
`complete: true`, 0 missing, 0 extra, 0 duplicate citation paths (also checked directly on
the provisions JSONL: 341 unique). Source PDFs 2.7 MB, SHA-256 matches the inventory.

Artifacts (unsigned, awaiting controller):

- `data/corpus/sources/us/manual/2026-09-10-medicare-cms-iom-100-01/official-documents/us-cms-iom-100-01-chapter-<n>.pdf` (n = 1..7)
- `data/corpus/inventory/us/manual/2026-09-10-medicare-cms-iom-100-01.json`
- `data/corpus/provisions/us/manual/2026-09-10-medicare-cms-iom-100-01.jsonl`
- `data/corpus/coverage/us/manual/2026-09-10-medicare-cms-iom-100-01.json`

Rebuild:

```bash
uv run python scripts/build_cms_iom_100_01_manifests.py   # reads the IOM index, writes the manifest and queue
uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-10-medicare-cms-iom-100-01 --manifest manifests/us-cms-iom-100-01.yaml \
  --source-as-of 2026-09-10
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
→ 255 passed, 2 skipped, 10 failed. All 10 failures are `FileNotFoundError` on retained
`data/corpus/...` artifacts absent from this sparse worktree (test_be_rulespec_2026_08_23_promotion,
test_build_ny_tanf_compatibility_scope ×2, test_rulespec_be_source_promotion, test_us_ak/ct/mi/mt/nd/ny
SNAP manual tests); none touch the official-documents extractor or the files in this commit.

## Reviewer judgments

1. Section paths are flat under the chapter (`chapter-3/10.4.3.1`, all level 2), as the work
   order's `chapter-<n>/<section>` pattern reads. Nesting by label (`10/10.4/10.4.3/10.4.3.1`)
   would need extractor code (no hierarchical label template exists); the label itself carries
   the hierarchy.
2. The bold transmittal line under each heading is kept as the first line of the body
   (source text, section-level provenance). Chapter 6 §160's heading includes
   "(Rev. 1, 09-11-02)" because the PDF prints it on the heading line.
3. Chapter 3 §10 "Hospital Insurance (Part A)" is a container heading with no text in the
   source; it is emitted with an empty body. Chapter 5 §10.1.10 and chapter 6 §§20, 140.4.5
   have no transmittal line in the source.
4. Chapter 7's TOC lists §10 and §20 as "Not yet available"; the PDF has no such sections, so
   none are emitted (58 sections against 60 TOC entries). Chapter 2's body carries eight
   sections its TOC omits (40.3.4-40.3.7.5); the body governs (67 against 59).
5. `expression_date` = latest TOC transmittal issued date per chapter, so the seven chapters
   carry dates from 2019-05-17 to 2025-04-17. If the release wants one date per scope, rerun
   with `--expression-date 2026-09-10` after removing the per-document values.
6. The Crosswalks PDF on the Pub 100-01 page (old-to-new section map) is a finding aid and is
   not taken; the same applies to the crosswalks on the other publication pages.
7. Later families (not taken; each would be its own version): Pub 100-24 State Payment of
   Medicare Premiums (6 chapters, the Part A/Part B buy-in manual; the most direct CMS-manual
   source for Medicare Savings Program administration and a strong next family); Pub 100-02
   Medicare Benefit Policy Manual (17 chapters, benefit coverage rules); Pub 100-04 Medicare
   Claims Processing Manual (41 chapters; only a few chapters touch premiums/deductibles, and
   Pub 100-01 ch. 3 already carries the deductible, coinsurance and Part B premium text);
   Pub 45 State Medicaid Manual (paper-based, 12 chapter ZIPs; ch. 3 Eligibility holds the MSP
   material; ZIP is not a format the official-documents extractor reads, so it needs an adapter
   or a pre-unpack step). Same heading style (bold "N - Title") is expected across IOMs, so the
   generator's approach should transfer, but each publication must be proven separately.
8. Lead-list items outside this family: cms.gov yearly premium/deductible fact sheets and the
   2021 press release (candidate `guidance` family, one document per year), medicare.gov cost
   pages (consumer site, judgment needed on whether they count as primary), SMD letter
   smd10003.pdf (official CMS State Medicaid Director letter, candidate `guidance`), SSA POMS
   SI 01715.010 (SSA family), Maine 22 MRS §3174-LLL, Massachusetts EOM 24-03 and Missouri
   IMAN 0865.010.15 (state families). The existing `us/guidance/cms/original-medicare-part-a-b`
   scope was not re-ingested.
9. The continuation pattern is a regex heuristic for Title-Case lines; it can only misfire on
   the first body line of a section with no transmittal line (5 sections, listed above, all
   checked clean). A future chapter revision could add such a case; the generator prints TOC
   section counts per chapter for comparison at rebuild time.

Remaining (controller): `sign-ingest-manifest` for the scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2); nothing here was pushed, signed,
published or loaded.
