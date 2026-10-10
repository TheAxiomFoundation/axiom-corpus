# CHIP state eligibility manuals, handbook chapters and adopted rules, batch 4 (US-network retry)

Date: 2026-09-10
Program: CHIP (board Year 1 list; `manifests/chip-agent-queue.yaml`)
Branch: `discovery/ingest-chip` (continues docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals-batch-3.md)

Timing: started_at 2026-09-10T21:33:26Z, finished_at 2026-09-10T22:13:57Z, agent wall time 40 min 31 s.
GitNexus impact analysis was not run: the GitNexus MCP tools were not available in this session. No
adapter or library function was modified and no new adapter was needed. The only code change is in
`scripts/build_chip_state_eligibility_manifests.py`: batch-4 dictionaries (`CONFIRMED_BATCH4`,
`BLOCKED_BATCH4`, `DONE_BATCH4`, `NEW_ROW_NAMES_BATCH4`, `RETRY_NOTES_BATCH4`), the extraction
constants for the new scopes, three topic lists (`UT_CHIP_TOPICS`, `AK_MAGI_TOPICS`, `ND_ACA_TOPICS`)
read from the publishers' own tables of contents, four small helpers (`_topic_slug`, `_ut_topic_doc`,
`_ak_topic_doc`, `_nd_topic_doc`), an `import re`, and five small edits in `main()` (the batch-4 merges
and a skip so a row unblocked in batch 4 is not re-blocked by its batch-1/2/3 entry). Batch-1, -2 and
-3 manifests regenerate byte-identical (git shows only the queue, the script and the eight new
manifests). `uv run ruff check scripts/build_chip_state_eligibility_manifests.py` passes.

Source family and conventions are batch 1's: the state agency's own CHIP eligibility manual, handbook
chapter, or adopted eligibility rule (or the combined Medicaid eligibility manual chapters / MAGI rules
that govern Medicaid-expansion CHIP), confirmed from the publisher's own index; document_class `manual`
(or `regulation` for an adopted rule); version `2026-09-10-chip-state-eligibility-manual`; citation
paths `us-xx/manual/<agency>/<program>/<section>`, regulation scopes following each jurisdiction's
existing regulation citation convention. CMS state plan amendments were not re-ingested. A state whose
CHIP rules are already in the corpus under a combined manual, including the parallel Medicaid run's
scopes written to the same corpus root today, is done with a pointer.

Work order: (1) retry every `blocked_primary_source` row (14: FL, KS, LA, WI, CA, OH, AZ, SC, OR, NE,
HI, NH, UT, MT) now that the controller's network exits from a US address: one plain request plus one
chrome120 browser-impersonation request, 20 s timeouts, at 2026-09-10T21:35Z; where the publisher
answers, confirm the source on its own index, inventory it, extract, verify; (2) then the five
never-queued jurisdictions AK, DC, ND, VT, WY. Twelve rows were extracted at first (LA, OH, SC, OR,
NE, HI, NH, UT, KS, AK, ND, VT); while they ran, the parallel Medicaid run (branch
`discovery/ingest-medicaid`, same corpus root) wrote us-la, us-oh, us-sc, us-ks and us-az Medicaid
scopes (22:02-22:05Z) that contain the same CHIP documents, so LA, OH, SC and KS were converted to
done-by-pointer and their CHIP artifacts deleted (LA's four documents collided path-for-path with the
Medicaid scope; OH, SC and KS were the same text under another scope), and AZ moved from blocked to
done-by-pointer. Eight jurisdictions were extracted for CHIP.

## Result

| Jurisdiction | Retry (plain / chrome120) | Status | Scope | Index docs | Taken | Provisions | Extract s |
|---|---|---|---|---|---|---|---|
| us-fl | 404 / 404 (page removed) | blocked_primary_source | - | 14 (FHKC pages) | 0 | - | - |
| us-ks | 403 / 404 -> manuals page 200 | done (pointer, Medicaid run) | us-ks/manual (medicaid) | 30 | 0 | - | - |
| us-la | 403 / 200 | done (pointer, Medicaid run) | us-la/manual (medicaid) | 99 | 0 | - | - |
| us-wi | 200 / 200 | done (pointer, Medicaid run) | us-wi/manual (medicaid) | 53 | 0 | - | - |
| us-ca | 200 Incapsula challenge / same | blocked_primary_source | - | n/a | 0 | - | - |
| us-oh | 200 / 200 | done (pointer, Medicaid run) | us-oh/manual (medicaid) | 6 | 0 | - | - |
| us-az | 200 stub / 200 stub | done (pointer, Medicaid run) | us-az/manual (medicaid) | 743 | 0 | - | - |
| us-sc | 200 / 200 (chain repaired) | done (pointer, Medicaid run) | us-sc/manual (medicaid) | 19 | 0 | - | - |
| us-or | 200 / 200 (shell) | agent_ready | us-or/regulation | 40 | 1 | 41 | 3 |
| us-ne | 404 / 404; SoS API 200 (chain repaired) | agent_ready | us-ne/regulation | 29 | 1 | 43 | 2 |
| us-hi | 404 / 404 -> DHS rules index 200 | agent_ready | us-hi/regulation | 140 | 2 | 25 | 3 |
| us-nh | 200 / 200 | agent_ready | us-nh/regulation | 1 | 1 | 157 | 3 |
| us-ut | 200 / 200 | agent_ready | us-ut/manual | 909 | 206 | 436 | 78 |
| us-mt | 405 CAPTCHA / same | blocked_primary_source | - | n/a | 0 | - | - |
| us-ak | (new) 200 | agent_ready | us-ak/manual | 64 | 64 | 128 | 16 |
| us-dc | (new) 200, postback-only text | blocked_primary_source | - | 19 | 0 | - | - |
| us-nd | (new) 200 | agent_ready | us-nd/manual | 141 | 133 | 268 | 29 |
| us-vt | (new) 200 | agent_ready | us-vt/regulation | 26 | 2 | 55 | 5 |
| us-wy | (new) 200, postback-only listing | blocked_primary_source | - | n/a | 0 | - | - |

Hosts retried: 14 (all 14 blocked rows) plus the 5 new jurisdictions' publishers. Extracted 8
jurisdictions (410 documents, 1,153 provisions of which 743 sections/pages/blocks below the document
records); done-by-pointer 6 (WI, LA, OH, SC, KS, AZ); still blocked 5 (CA, MT, FL, DC, WY). Index
documents found on the eight extracted publishers' indexes: 1,350; taken 410. Coverage `complete: true`
for every extracted scope, 0 missing, 0 extra, 0 duplicate citation paths and 0 duplicate source
citations. Uniqueness was re-verified directly on each provisions JSONL; every new citation path was
checked against every other provisions JSONL under `data/corpus/provisions/<jurisdiction>/` (0
cross-scope collisions for the eight kept scopes; the LA collision above is why LA was not kept). Every
inventory item names an existing non-symlink regular file under the exact
`sources/<jurisdiction>/<class>/2026-09-10-chip-state-eligibility-manual/` boundary with a matching
SHA-256, and every provision's source path is in its inventory. Extraction configurations were proven
before the full runs on the publishers' own bytes with the library extractor (`_extract_blocks` on the
probe snapshots) instead of scratch-base smoke runs, to finish while the route held; the full runs
matched those results exactly. Extract seconds are wall seconds of the final `extract-official-documents`
command. Queue status_counts after this batch: done 14, agent_ready 33, blocked_primary_source 5
(52 rows including the federal row).

The LA, OH, SC and KS extractions that were deleted had run clean (coverage complete; LA 38, OH 12,
SC 140, KS 390 provisions, 2-4 s each); their configurations are kept in this note's per-jurisdiction
entries so a reviewer preferring section granularity for SC (139 labeled sections vs the Medicaid
run's chapter level) or KS (389 numbered sections vs 117 chapter pages) can re-run them.

Artifacts (unsigned, uncommitted, awaiting controller; `data/corpus` lives in the main checkout, the
worktree is sparse):

- `data/corpus/sources/us-xx/<class>/2026-09-10-chip-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`

for us-ut, us-ak, us-nd (manual) and us-or, us-ne, us-hi, us-nh, us-vt (regulation).

TLS: verification was never disabled and no `request: verify_tls` key is used. img1.scdhhs.gov (Go
Daddy Secure Certificate Authority - G2) and rules.nebraska.gov (DigiCert Global G2 TLS RSA SHA256 2020
CA1) still serve their leaf without the issuing intermediate; both intermediates were already committed
under `data/certs/` (batches 2 and 3) and were used through REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE
(certifi + `data/certs/*.pem`, assembled in the scratch directory), after which both hosts answer HTTP
200. `data/certs` is unchanged. dpaweb.hss.state.ak.us is HTTP-only (as in us-ak-snap-manual.yaml).
Hosts read through the manifest `request: browser_impersonation: true` fallback: none of the eight kept
scopes (every publisher answers the plain client; the OARD in fact serves only a shell to the chrome120
client, so impersonation must not be used there).

Rebuild:

```bash
uv run python scripts/build_chip_state_eligibility_manifests.py
export REQUESTS_CA_BUNDLE=<certifi cacert.pem + data/certs/*.pem> CURL_CA_BUNDLE=$REQUESTS_CA_BUNDLE
for j in or ne hi nh ut ak nd vt; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-chip-state-eligibility-manual \
    --manifest manifests/us-$j-chip-state-eligibility-manual.yaml --source-as-of 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. The 10 failures are the known sparse-worktree failures (BE rulespec
promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual tests), all
`data/corpus` artifacts absent from this worktree; none touch CHIP files.

## Per-jurisdiction index inventories

- **us-fl** (blocked) ahca.myflorida.com now answers, but the Florida KidCare page is HTTP 404
  "WebContentNotFound" at /medicaid/florida-kidcare, /medicaid/florida-kidcare.html and under
  medicaid-policy-quality-and-operations; the Medicaid and Medicaid Policy, Quality and Operations pages
  (HTTP 200) carry no KidCare or Title XXI eligibility manual or rule link. floridakidcare.org (14
  consumer pages, batch 1) publishes no manual; the DCF ESS manual in the corpus has no KidCare chapter.
  0 taken; note appended.
- **us-ks** (done by pointer) www.kancare.ks.gov answers the chrome120 client (plain 403); the old
  eligibility-policy URL is 404 and the Policy Manuals page
  https://www.kancare.ks.gov/data-policy/policy/eligibility/manuals lists 30 manual links (July 2026
  KFMAM at khap.kdhe.ks.gov/kfmam/, plain HTTP 200; 29 MKEESM releases). The KFMAM site publishes the
  whole manual on one page (main.asp). The Medicaid run ingested the KFMAM (117 chapter-page documents,
  757 provisions) at us-ks/manual/kdhe/medicaid/kfmam-*; CHIP is section 1102 and the family medical
  determinations throughout. Deleted CHIP config (for a reviewer): `div.right-content-large`, labeled
  sections `^(?P<label>\d{4,5})\s+(?P<heading>(?:\d{4,5}\s+)?[A-Z][^-]*?)\s+-(?:\s+(?P<body>.*))?$`,
  389 sections, expression_date 2026-07-01.
- **us-la** (done by pointer) https://ldh.la.gov/page/medicaid-eligibility-manual (chrome120 200, plain
  403; PDFs plain 200): 99 PDFs (38 H eligibility-determination chapters, 25 I eligibility factors, 17 Z
  charts, 19 other sections). LaCHIP is H-3030 (issued 2023-08-11), H-3040 LaCHIP Affordable Plan
  (2025-03-24), H-3050 LaCHIP Phase IV (2023-05-01), Z-2500 premium-program FPIG (2026-02-02). The
  Medicaid run ingested all 99 (891 provisions) at us-la/manual/ldh/medicaid/*, the same citation paths
  this run's four-document extraction produced (6 colliding paths), so the CHIP artifacts were deleted.
  Deleted CHIP config: label-only lines `^\s*(?P<num>H-30[345]\d(?:\.\d+)?)\s*$` with a following
  heading line, per-page manual header lines dropped, Z-2500 page-level.
- **us-wi** (done by pointer) https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm answers HTTP 200
  (plain and chrome120); the BadgerCare Plus Eligibility Handbook TOC (whxdata/toc.new.js) lists 53
  chapters in 6 books. The same handbook, as DHS publication PDF p10171-26-03 (Release 26-03), is in the
  Medicaid run's us-wi/manual/dhs/medicaid/badgercare-plus-handbook-release-26-03 (330 page provisions;
  alongside meh-release-26-03, 503). Nothing separate to add.
- **us-ca** (blocked) www.dhcs.ca.gov MEPM index: HTTP 200 whose 843-byte body is an Incapsula "Request
  unsuccessful" JavaScript-challenge iframe, plain and chrome120. 0 taken; note appended.
- **us-oh** (done by pointer) https://codes.ohio.gov/ohio-administrative-code/chapter-5160:1-4 (HTTP 200
  plain and chrome120): 6 rules 5160:1-4-01 to -06 (Effective 2026-06-01, 2026-06-01, 2026-06-01,
  2024-03-01, 2025-10-06, 2024-01-01). The Medicaid run ingested all OAC 5160:1 eligibility rules (96
  documents, 192 provisions) at us-oh/manual/odm/medicaid/5160-1-*, including these six, so this run's
  us-oh/regulation extraction (6 documents, `section.laws-body`) was deleted as duplicate text.
- **us-az** (done by pointer) epm.azahcccs.gov answers HTTP 200 but its root is a 158-byte stub; /EPM/,
  /index.htm, /Default.htm 404; www.azahcccs.gov's EligibilityPolicy and shared/EPM pages are "Page/
  Document not found"; the manual lives at https://epm.azahcccs.gov/EligibilityPolicyManual/index.html,
  from which the Medicaid run ingested the whole AHCCCS Eligibility Policy Manual (743 topic documents,
  4,712 provisions) at us-az/manual/ahcccs/medicaid/*, including 408 KidsCare, 528 B Premium Payment for
  KidsCare, 1204 KidsCare Premiums and 1308 KidsCare Application Process. apps.azsos.gov (A.A.C. 9-31)
  still returns the Cloudflare challenge (HTTP 403).
- **us-sc** (done by pointer) https://img1.scdhhs.gov/mppm/ (HTTP 200 with the committed Go Daddy G2
  intermediate): 19 documents (sections 100, 200, 300, 800; chapters 401-406, 501-504, 601, 701-703; the
  MIAP Manual) plus SharePoint training links. Partners for Healthy Children is Chapter 204.03 of
  Section_200.docx (latest revision 2026-08-01). The Medicaid run ingested the 18 MPPM documents at
  chapter level (68 provisions) at us-sc/manual/scdhhs/medicaid/*, including section-200, so this run's
  139-section extraction was deleted as duplicate text. Deleted CHIP config (docx labeled sections):
  `^(?P<label>20\d\.\d\d(?:\.\d\d[A-Z]?)?)\s+(?P<heading>(?!.*\s\d{1,3}$)[A-Z].*|Family Planning for
  Minors Under Age 19)$` with `start_after_pattern` `^CHAPTER 201—MAGI Introduction$` (each chapter's own
  table of contents repeats the headings with a trailing page number; two body headings legitimately end
  in a digit).
- **us-or** OARD (plain client HTTP 200; the chrome120 client receives a 5 KB shell). Batch 3's
  selectedChapter=94 was Oregon State Police; OAR chapter 410 (OHA Health Systems Division: Medical
  Assistance Programs) is selectedChapter=87 with 39 divisions. Division 200 Eligibility for Health
  Systems Division Medical Programs https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=1742
  lists 40 rules 410-200-0010 to 410-200-0521 with full text on one page (latest effective 2026-03-01;
  one family). Taken 1 (the division page, `#content`, labeled `410-200-NNNN Heading`), 40 rule sections.
- **us-ne** dhhs.ne.gov answers (the Medicaid-Regulations page is 404); rules.nebraska.gov (chain
  completed with the committed DigiCert intermediate) chapter API
  https://rules.nebraska.gov/api/chapter/GetByTitleId/232 (Title 477 Medicaid Eligibility, agency 37,
  same mechanism as us-ne-snap-rules.yaml): 29 chapters (one family). Nebraska's 599 CHIP is
  Medicaid-expansion coverage under 477 NAC 14-19 (MAGI-based programs). Taken 1: 477 NAC 19 MAGI-Based
  Programs (effective 2020-07-29; blob `477 NAC 19 (07-29-2020).pdf`), 42 labeled sections with the 475
  NAC pattern. Not taken: chapters 14-18 (2018 filings in the older `15-004` numbering) and the non-MAGI
  chapters. No `verify_tls: false` (the SNAP manifest's setting) was used.
- **us-hi** medquest.hawaii.gov answers (har.html 404; its Rules & Policies page links the DHS index)
  https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/: 140 chapter PDFs (49 Med-QUEST
  subtitle 12 chapters 17-1700.1 to 17-1739; 91 other Title 17 chapters). Taken 2: HAR 17-1715 Children
  Group (8 pages) and 17-1724.2 MAGI-Based Income Methodology (15 pages), amended and compiled 2016-11-10;
  scanned PDFs with an OCR text layer, so page-level as in us-nv. Not taken: 17-1714.1, 17-1711.1, the
  income-standards charts.
- **us-nh** https://www.gencourt.state.nh.us/rules/state_agencies/he-w800.html now answers HTTP 200
  (redirecting to gc.nh.gov, the host of us-nh-snap-rules.yaml): Chapter He-W 800 Eligibility for Medical
  Assistance is one HTML document (33 parts; latest amendment effective 2025-10-01). Taken 1, the He-W
  700 labeled-section configuration, 156 sections, stop at Appendix A.
- **us-ut** https://oepmanuals-chip.dhhs.utah.gov/ answers HTTP 200 (plain and chrome120). The separate
  CHIP Policy Manual (effective 2024-05-01; What's New through September 2026) is a RoboHelp site;
  whxdata/toc.new.js and 63 nested toc files list 909 topic pages: 206 current manual topics (100 General
  Provisions 28, 200 Program Standards 42, 400 Income Standards and Household Composition 61, 600 Program
  Benefits 5, 700 Eligibility Determination and Redetermination 26, 800 Records and Case Management 17,
  1000 State CHIP 16, Tables 11), 697 Obsolete topics, 3 FAQ, Glossary, Welcome, What's New. Taken 206
  (every current topic; `body` with `div.topic-header` dropped; one block each, 24 topics yield two
  blocks). Each topic states its own Effective Date; expression_date is source_as_of.
- **us-mt** (blocked) rules.mt.gov now answers HTTP 405 with a "Human Verification" CAPTCHA page
  requiring JavaScript, plain and chrome120. 0 taken; note appended.
- **us-ak** (new) http://dpaweb.hss.state.ak.us/manuals/ (HTTP only): directory of DPA manuals; the MAGI
  Medicaid Eligibility Manual (MAGI2/, WebHelp) governs Denali KidCare (Medicaid-expansion CHIP; 816 MAGI
  Medicaid Categories). Its TOC whdata/whtdata0-14.htm has 108 entries pointing at 64 topic pages
  (sections 800-833). Taken 64 (`body` with the topic header dropped). health.alaska.gov's
  policy-manuals page is 404. No manual-wide date; expression_date is source_as_of.
- **us-dc** (blocked) dcregs.dc.gov 29 DCMR Chapter 95 Medicaid Eligibility
  https://dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-95: 19 sections 29-9500 to 29-9599 (HTTP
  200; SectionList and RuleDetail pages answer, e.g. R0054304 effective 2024-03-08) but every rule text and
  PDF is behind ASP.NET `__doPostBack` form posts with no GET URL; not emulated. dhcf.dc.gov requires
  JavaScript. 0 taken.
- **us-nd** (new) https://www.nd.gov/dhs/policymanuals/51003/ (MadCap; release 26.3 published
  2026-05-15; hhs.nd.gov's manual URLs are 404): Service Chapter 510-03 Eligibility Factors for ACA
  Medicaid, under which Healthy Steps (Medicaid-expansion CHIP) is determined (the Healthy Steps manual is
  archived inside it). Data/Tocs/Master_Chunk0.js lists 141 entries: 133 policy topics 510-03-05 to
  510-03-105-15 plus 8 archive/site pages. Taken 133 (`#mc-main-content`), expression_date 2026-05-15.
- **us-vt** (new) https://humanservices.vermont.gov/rules-policies/health-care-rules/health-benefits-eligibility-and-enrollment-rules-hbee:
  26 PDFs (8 adopted HBEE parts, combined rules 2025-12-17, one ARPA GCR, 10 proposed drafts, 5 repealed
  legacy rules, one other). Dr. Dynasaur is determined under the HBEE Rules. Taken 2: Part 2 Eligibility
  Standards (27 sections) and Part 5 Financial Methodologies (26 sections), labeled `N.NN Heading
  (mm/dd/yyyy, GCR nn-nnn)` from page 3 with the running header dropped; latest GCR 2026-01-01 each.
- **us-wy** (blocked) rules.wyo.gov answers HTTP 200 but its agency listing, search and downloads are
  ASP.NET postbacks (no GET listing or file URL); health.wyo.gov/healthcarefin/chip/ publishes member
  pages only (Does My Child Qualify, copays, renewal, FAQ, handbooks); programs-and-eligibility is 404.
  0 taken.

## Reviewer judgments

1. **Medicaid-run pointers for LA, OH, SC, KS, AZ.** The parallel Medicaid run wrote these scopes
   while this batch was extracting the same documents. Following the rule that a state covered by a
   combined manual (including today's Medicaid scopes) is done with a pointer, the CHIP extractions were
   deleted rather than kept as second copies; LA would otherwise have carried six duplicate citation
   paths across scopes. The deleted configurations are recorded above. If the Medicaid branch is not
   merged or is cut differently, these five rows (and WI, AR, NC, NJ, VA from earlier batches) need
   revisiting.
2. **Granularity lost by pointing.** The Medicaid run holds SC Section 200 at chapter level (68
   provisions for 18 documents) and the KFMAM at chapter-page level; this run's labeled extractions
   (139 and 389 sections) were finer. A reviewer may prefer to re-run them under the CHIP version.
3. **Utah as 206 topic documents.** The whole separate CHIP manual is taken topic by topic (the
   publisher's TOC unit) with source_as_of as expression_date, because each topic carries its own
   Effective Date line and the manual publishes no single date. Obsolete (697), FAQ, Glossary, Welcome
   and What's New topics were not taken.
4. **Alaska and North Dakota as whole MAGI manuals.** Both states determine their CHIP under a
   MAGI/ACA Medicaid manual; every policy topic was taken (64 and 133) as for Utah. ND's expression
   date is the manual's last publication date; AK's is source_as_of.
5. **Oregon, Nebraska, New Hampshire, Hawaii, Vermont** take the MAGI rules that govern
   Medicaid-expansion CHIP children (OR division 200; NE 477 NAC 19 only, not the 2018 chapters 14-18;
   NH the whole He-W 800 chapter; HI 17-1715 and 17-1724.2; VT HBEE parts 2 and 5), as in batch 3.
6. **Hawaii dates and OCR.** 17-1715 and 17-1724.2 are scanned PDFs (OCR text layer with artifacts such
   as "$ubchapter"); page-level provisions; expression_date is the "am and comp NOV 10 2016" compilation
   date rather than the index file name's 10-31-16.
7. **Oregon rule ids.** The division page's citation suffixes are the rule numbers
   (`.../division-200/410-200-0010`), not the Oregon adapter's `rule-410-200-0010` form; the expression
   date is the latest effective date on the page (2026-03-01), each rule's own history is in its text.
8. **No scratch-base smoke runs.** Configurations were validated on the probe snapshots with the library
   extractor before the full runs; the full runs reproduced those block counts exactly.
9. **DC and Wyoming** are recorded as blocked although their sites answer: rule text is reachable only
   through ASP.NET postbacks, which the official-documents extractor cannot issue and this run did not
   emulate. A reviewer may prefer a distinct status or an adapter.
10. **Florida** stays blocked with a different failure (page removed, no manual located); the candidate
    remains s. 409.814 F.S. from the Legislature.
11. **KY, NM, TN** also received Medicaid-run manual scopes today (not inspected here); their CHIP rows
    hold separate regulation scopes from batches 2-3 and were not changed.
12. **Serving overlap.** us-ut/manual, us-ak/manual, us-nd/manual, us-hi/regulation, us-ne/regulation,
    us-nh/regulation share their `(jurisdiction, document_class)` pair with existing scopes; the
    controller must include both versions in a release's membership when activating. us-or/regulation
    and us-vt/regulation are new pairs.

## Closing status (51 jurisdictions)

| Jurisdiction | Status | Scope | Version | Index docs | Taken |
|---|---|---|---|---|---|
| us-ak | agent_ready | us-ak/manual | chip | 64 | 64 |
| us-al | agent_ready | us-al/manual | chip | 17 | 2 |
| us-ar | done | us-ar/manual | medicaid run | 1 | 0 |
| us-az | done | us-az/manual | medicaid run | 743 | 0 |
| us-ca | blocked_primary_source | - | - | n/a | 0 |
| us-co | agent_ready | us-co/regulation | chip | 22 | 1 |
| us-ct | agent_ready | us-ct/manual | chip | 9 | 2 |
| us-dc | blocked_primary_source | - | - | 19 | 0 |
| us-de | agent_ready | us-de/regulation | chip | 1 | 1 |
| us-fl | blocked_primary_source | - | - | 14 | 0 |
| us-ga | agent_ready | us-ga/manual | chip | 241 | 1 |
| us-hi | agent_ready | us-hi/regulation | chip | 140 | 2 |
| us-ia | agent_ready | us-ia/manual | chip | 58 | 1 |
| us-id | agent_ready | us-id/regulation | chip | 2 | 1 |
| us-il | done | us-il/manual | 2026-05-27-il-cash-snap-medical-manual-r2026-07-15-self-contained | 14 | 0 |
| us-in | agent_ready | us-in/manual | chip | 24 | 2 |
| us-ks | done | us-ks/manual | medicaid run | 30 | 0 |
| us-ky | agent_ready | us-ky/regulation | chip | 2 | 2 |
| us-la | done | us-la/manual | medicaid run | 99 | 0 |
| us-ma | agent_ready | us-ma/regulation | chip | 2 | 2 |
| us-md | agent_ready | us-md/regulation | chip | 17 | 17 |
| us-me | agent_ready | us-me/regulation | chip | 6 | 1 |
| us-mi | done | us-mi/manual | 2026-07-17-mi-bridges-manual | 196 | 0 |
| us-mn | agent_ready | us-mn/manual | chip | 23 | 2 |
| us-mo | agent_ready | us-mo/manual | chip | 28 | 2 |
| us-ms | agent_ready | us-ms/manual | chip | 27 | 3 |
| us-mt | blocked_primary_source | - | - | n/a | 0 |
| us-nc | done | us-nc/manual | medicaid run | 64 | 0 |
| us-nd | agent_ready | us-nd/manual | chip | 141 | 133 |
| us-ne | agent_ready | us-ne/regulation | chip | 29 | 1 |
| us-nh | agent_ready | us-nh/regulation | chip | 1 | 1 |
| us-nj | done | us-nj/manual | medicaid run | 6 | 0 |
| us-nm | agent_ready | us-nm/regulation | chip | 4 | 4 |
| us-nv | agent_ready | us-nv/manual | chip | 93 | 2 |
| us-ny | agent_ready | us-ny/manual | chip | 8 | 1 |
| us-oh | done | us-oh/manual | medicaid run | 6 | 0 |
| us-ok | agent_ready | us-ok/regulation | chip | 397 | 1 |
| us-or | agent_ready | us-or/regulation | chip | 40 | 1 |
| us-pa | agent_ready | us-pa/manual | chip | 16 | 1 |
| us-ri | agent_ready | us-ri/regulation | chip | 4 | 2 |
| us-sc | done | us-sc/manual | medicaid run | 19 | 0 |
| us-sd | agent_ready | us-sd/regulation | chip | 13 | 2 |
| us-tn | agent_ready | us-tn/regulation | chip | 22 | 1 |
| us-tx | agent_ready | us-tx/manual | chip | 23 | 1 |
| us-ut | agent_ready | us-ut/manual | chip | 909 | 206 |
| us-va | done | us-va/manual | medicaid run | 21 | 0 |
| us-vt | agent_ready | us-vt/regulation | chip | 26 | 2 |
| us-wa | agent_ready | us-wa/manual | chip | 16 | 1 |
| us-wi | done | us-wi/manual | medicaid run | 53 | 0 |
| us-wv | done | us-wv/manual | 2026-07-21-wv-income-maintenance-manual | 1 | 0 |
| us-wy | blocked_primary_source | - | - | n/a | 0 |

"chip" = version 2026-09-10-chip-state-eligibility-manual; "medicaid run" = 2026-09-10-medicaid-state-eligibility-manual
on branch discovery/ingest-medicaid. status_counts: done 14, agent_ready 33, blocked_primary_source 5
(plus the federal `us` row, done). Blocked: CA (Incapsula challenge), MT (CAPTCHA), FL (page removed, no
manual located), DC and WY (postback-only publishers).

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2). Not done here: push, sign, publish,
Supabase load.
