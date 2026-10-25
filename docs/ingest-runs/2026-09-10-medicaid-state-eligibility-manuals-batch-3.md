# Medicaid state eligibility manuals, batch 3

Date: 2026-09-10
Program: Medicaid (board Year 1 list; `manifests/medicaid-agent-queue.yaml`)
Agent: two sessions. The first agent ran roughly 2026-09-10T19:40Z to 20:40Z (probing, the sixteen queue rows, the
batch-3 generator section and six manifests) and was killed before extracting anything. This continuation picked
up from the state on disk: started_at 2026-09-10T20:43:08Z, finished_at 2026-09-10T21:09:36Z, wall time 0h 26m 28s (this
session only; the first session's hour is additional).
Impact analysis: not run; the GitNexus MCP tools were unavailable in both sessions. No function in
`src/axiom_corpus` was modified and no adapter was added. The only code change is to the batch-1/2 generator
`scripts/build_medicaid_state_eligibility_manual_manifests.py`: five new `build_xx()` functions (OK, CT, IA, NV,
MS), a `document3()` wrapper (batch-3 provenance string), batch-3 static rows (nine blocked, two done pointers),
a `_ok_rule_from_page()` helper added in this session (below), and `--batch 3` in `main()`. Batch-1 and batch-2
builders and rows are untouched (`--batch 3 --only ...` was used for every regeneration).

## Batch selection (reviewer judgment)

Batch 3 = the next ten states by population after batch 2: SC, AL, LA, KY, OR, OK, CT, UT, IA, NV, with
MS, KS, NM, NE, ID, WV as replacements, in that order. Every publisher was probed once by the first agent
(plain request plus curl-cffi chrome120 browser impersonation, 20 s timeouts). Nine block retrieval from this
network (SC, AL, LA, KY, OR, UT, KS, NM, NE; exact failures in the queue rows and below) and were replaced
immediately; ID and WV were found already covered by scopes in the corpus (`done`, pointers). The sixteen-state
probe cap was reached with five states attempted, so the batch falls short of the ten-attempted target by five;
no further replacement was pulled. Probed: 16. Attempted: OK, CT, IA, NV, MS (5). Extracted: 5. Blocked: 9.
Done pointers: 2. The blocked rows were not re-probed in this session.

Before each attempt, `manifests/` and `data/corpus/provisions/<jurisdiction>/` in the main checkout were checked
for a combined manual already carrying the Medicaid eligibility chapters: the CT SNAP scope is the separate SNAP
Policy Manual (portaldir.ct.gov), not the UPM; the IA scopes are Employees' Manual Title 7 (SNAP) and Title 5-E
(CHIP); the MS, NV and OK scopes are SNAP/TANF manuals and OAC 340 rules. Partial overlaps re-fetched under
Medicaid paths (the batch-2 CHIP precedent): 13 UPM sections that the CT SSP policy scope already holds under
`us-ct/policy/dss/upm/...` (4005.05, 4005.10, 4520.10, 4520.20, 5000, 5030.10, 5030.15, 5045.10, 5050.13,
5520.10, 6000, 6000.01, 6005).

Family per state: the state Medicaid agency's eligibility policy manual (MAGI and non-MAGI eligibility, income,
resources, household composition, LTSS financial eligibility), confirmed from the agency's own index page;
transmittals, prior releases, omnibus duplicates, landing pages, other titles and other rule chapters on the
same index are separate families, inventoried but not taken.

Scope: document_class `manual`, version `2026-09-10-medicaid-state-eligibility-manual`, citation paths
`us-xx/manual/<agency>/medicaid/<section>`, `source_as_of` and `expression_date` 2026-09-10 (current manual
trees as fetched; effective dates printed inside the documents were not parsed; same judgment as batches 1
and 2).

Extraction: `uv run axiom-corpus-ingest extract-official-documents`, no new adapter, all artifacts under the
main checkout's `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus` (this worktree is sparse). PDFs use the
extractor's page granularity with `ocr: true`; HTML pages use `html_content_selector` per publisher; the CT
Word files use the extractor's existing `doc`/`docx` paths (legacy `.doc` is converted with macOS `textutil`;
the extractor also accepts `antiword` or `catdoc`, so a Linux rebuild needs one of those installed). TLS
verification was never disabled and no publisher needed a certificate bundle (no `data/certs` change). IA (14
PDFs, 14 s) was the smoke run for the PDF path and MS/NV followed; OK was the HTML path; CT the Word path.
Coverage is `complete: true` with 0 missing, 0 extra and 0 duplicate citation paths for every extracted scope;
`citation_path` uniqueness within each provisions JSONL and absence from every other provisions JSONL under
`data/corpus/provisions/<jurisdiction>/` (all document classes) were verified independently with a counter
script (0 in-file duplicates, 0 cross-scope collisions for all five scopes), and every manifest `source_url`
was checked against the written inventory.

## Per-jurisdiction results

| Jurisdiction | Index | Documents taken | Provisions | Extraction seconds |
| --- | --- | ---: | ---: | ---: |
| us-ia | HHS Employees' Manual, Income Maintenance manuals page (Title 8) | 14 | 1,199 | 14 (smoke, alone) |
| us-ms | DOM Eligibility Policy and Procedures Manual page | 29 | 984 | 44 |
| us-nv | DSS Medical Assistance Manual: contents, appendix, MTL pages | 33 | 481 | 25 |
| us-ok | OHCA rules, OAC 317:35 chapter page | 350 | 700 | 66 for the first 250 sections; 17 for the full 350 re-run |
| us-ct | DSS Uniform Policy Manual lists page, UPM0-UPM9 | 1,632 | 3,265 | 1,213 (background, 20 min 13 s) |

Timings after the IA smoke overlap: CT ran in the background for the whole session while OK, MS, NV and the OK
re-run were extracted alongside it, so the per-state seconds are wall seconds under shared network and CPU.

Total: 2,058 documents, 6,629 provisions across 5 scopes. Index documents found versus taken are in
the queue rows (`index_document_count`, `taken_count`, `index_families`): found 2,516 across the five extracted
indexes, taken 2,058.

### Index inventories (every document family on the publisher index; taken counts)

**us-ok** — https://oklahoma.gov/ohca/policies-and-rules/xpolicy/medical-assistance-for-adults-and-children-eligibility.html
Oklahoma publishes no separate eligibility manual; Medicaid eligibility is OAC 317:35 (Chapter 35, Medical
Assistance for Adults and Children - Eligibility), which OHCA publishes section by section on oklahoma.gov. The
chapter page carries the whole tree: section pages 350 found / 350 taken; subchapter landing pages 17 / 0; part
landing pages 29 / 0 (link lists). 396 found, 350 taken. Selector `main#main`, dropping the page title block, the
child-page list and the "back to policy" paragraph. Citation paths `us-ok/manual/ohca/medicaid/317-35-5-41`
(the OAC number). The chapter page labels most sections with their OAC number or "SECTION n. Title", but 100
sections in subchapters 9 (ICF/IID, HCBW/IID, 65+ in mental health hospitals), 10 (other eligibility factors for
families with children and pregnant women), 11, 15 (personal care), 17 (nursing facility) and 19 (ADvantage) are
labelled by title alone or as "35-10-10. Title"; the first agent's builder skipped those 100 with a stderr
message and its queue row recorded 350 found / 250 taken. This session added `_ok_rule_from_page()`, which reads
each not-explicitly-numbered section's OAC number from the section page itself (the page opens with
"317:35-9-45. ...") and reports any disagreement with a "SECTION n" chapter-page label: 0 disagreements, so the
250 documents already generated were unchanged (byte-identical in the manifest) and the 100 were added, many of
them `[REVOKED]`, `[TERMINATED]` or `[RESERVED]` stubs that carry only the revocation line. OHCA labels two
different sections 317:35-16-3 and two 317:35-16-4 (personal-care and financial-eligibility sections); both of
each are kept, suffixed by page slug, with `publisher_numbering_duplicate: true`. The page footer says OHCA's web
rules are unofficial and the Secretary of State's OAC is the official text; recorded in `publisher_note`.

**us-ct** — https://portal.ct.gov/dss/lists/uniform-policy-manual
The DSS Uniform Policy Manual is the integrated eligibility manual for Medicaid (HUSKY A, C and D), cash
assistance (TFA, SAGA, State Supplement) and the Jobs First program; the lists page has one paginated sub-list
per chapter and one for policy transmittals, each item a Word file. UPM section documents (UPM0 Table of
Contents 26, UPM1 Rights and Responsibilities / Eligibility Process 178, UPM2 Assistance Unit Composition /
Categorical Eligibility 165, UPM3 Technical and Procedural Eligibility 229, UPM4 Treatment of Assets / Standards
of Assistance 216, UPM5 Treatment of Income / Income Eligibility 186, UPM6 Calculation of Benefits / Benefit
Issuance 106, UPM7 Benefit Error / Recovery 122, UPM8 Special Programs, SAGA, Jobs First 336, UPM9 Special
Benefits 68): 1,632 found / 1,632 taken (1,628 `.doc`, 4 `.docx`). Policy transmittals: 266 / 0. 1,898 found,
1,632 taken. Citation paths `us-ct/manual/dss/medicaid/4005-05` (UPM section number). Reviewer judgment: the
whole UPM is taken, including the cash-only chapters, because the UPM's chapters interleave the programs
section by section and the Medicaid rules cannot be cut out at chapter level; the 13 sections already in the
SSP policy scope are re-fetched here (see selection).

**us-ia** — https://hhs.iowa.gov/about/policy-manuals/income-maintenance
Employees' Manual Title 8 Medicaid chapter PDFs 8-A Administration, 8-B Application Processing, 8-C
Nonfinancial Eligibility, 8-D Resources, 8-E Income, 8-F Coverage Groups, 8-G Case Maintenance, 8-H Foster Care,
Adoption and Guardianship Subsidy, 8-I Medical Institutions, 8-J Medically Needy, 8-K Psychiatric Institutions,
8-L Aliens, 8-M Medicaid Services, 8-N Home- and Community-Based Waivers: 14 found / 14 taken. Title 8 omnibus
PDF (the same chapters in one file): 1 / 0. Other-title chapters and appendices on the same page (Titles 1-7,
9-17: SNAP, FIP, CHIP, child care, etc.): 71 / 0; other-title omnibus PDFs 2 / 0. 88 found, 14 taken. Citation
paths `us-ia/manual/hhs/medicaid/employees-manual-8-e`. Title 7 (SNAP) is already `us-ia/manual/hhs/em/7-x` and
Title 5-E is in today's CHIP scope.

**us-nv** — https://www.dss.nv.gov/programs/medical/medical-assistance-manual/
Division of Social Services (formerly DWSS) Medical Assistance Manual. Contents page: chapter PDFs A-100
Overview, A-200 Definitions, B-100 MAGI Categories, B-200 Specialized Categories, B-300 MAABD Categories, C-100
General Eligibility Requirements, D-100 to D-500 application processing, redeterminations, changes, E-100 to
E-400 budget methodologies, income and resources, F-100 to F-500 LTC, waivers, transfers, trusts, G-100
hearings, H-100 and H-200 hospital presumptive eligibility: 23 found / 23 taken; Table of Contents 1 / 1.
Appendix page: Appendices A-I (MAGI income charts, MAABD income standard and benefit level charts, BIC codes,
MAABD budgets, PRUCOL, RSDI, non-citizen documentation matrix): 9 / 9. Manual transmittal letters (MTL page
and the manual landing page): 72 / 0. 105 found, 33 taken. File URLs carry spaces and are percent-encoded in the
manifest. Citation paths `us-nv/manual/dss/medicaid/e-400`, `.../appendix-c`. The DWSS Eligibility and Payments
Manual already in the corpus (`us-nv/manual/dwss/eligibility-payments`) is the TANF/SNAP manual.

**us-ms** — https://medicaid.ms.gov/eligibility-policy-and-procedures-manual/
Division of Medicaid Eligibility Policy and Procedures Manual. Chapter PDFs 100 General Provisions, 101 Coverage
Groups and Processing Applications and Reviews, 102 Non-Financial Requirements, 200 Income, 300 Resources, 400
ABD and MAGI Eligibility Criteria and Budgeting, 500 Institutional Eligibility and Budgeting: 7 found / 7 taken.
Appendix A items A-1 to A-20 (need-standard and MAGI limit charts, COE chart, working-disabled premium scale,
trust guidelines and trust documents, life-expectancy and life-estate tables, COL history, student earned income
exclusion, notices and forms A-12 to A-16, ABD handouts, required-to-file worksheet, lottery winnings): 22 / 22.
No other uploads on the page. 29 found, 29 taken. Citation paths `us-ms/manual/dom/medicaid/chapter-400`,
`.../appendix-a-8-1`. Reviewer judgment: the notice and form appendices are taken because they are numbered items
of the manual's own Appendix A, not a separate forms library.

### Blocked publishers (recorded by the first agent, no workaround attempted, not re-probed here)

- **us-sc** — scdhhs.gov Medicaid Policy and Procedures Manual index: HTTP 403 (919-byte body, CloudFront) within
  1 s to both requests.
- **us-al** — medicaid.alabama.gov Eligibility Manual page: no TCP answer (ConnectTimeout; curl 28 at 20 s) for
  both requests.
- **us-la** — ldh.la.gov Medicaid Eligibility Manual page: HTTP 403 (4,542 and 4,903-byte bodies, cloudflare)
  within 1 s to both requests.
- **us-ky** — chfs.ky.gov DCBS Operation Manual page: HTTP 403 (1,484-byte body) within 1 s to both requests.
- **us-or** — the oregon.gov zone does not resolve from this network (NameResolutionError; curl 6; dig for
  www.oregon.gov, oregon.gov and secure.sos.state.or.us times out). The OPEN notebook already in the corpus
  (`us-or/manual/odhs/open`) is the ODHS integrated eligibility notebook, not the OHA OHP eligibility rules.
- **us-ut** — oepmanuals.dhhs.utah.gov (linked from medicaid.utah.gov/policy-manuals/ as the Medicaid
  Eligibility Policy Manual): HTTP 403 with an S3 AccessDenied body for the root and every common entry point;
  jobs.utah.gov (DWS InfoSource) HTTP 403 (awselb/2.0); medicaid.utah.gov itself is reachable but carries only
  provider manuals and training PDFs.
- **us-ks** — kancare.ks.gov eligibility policy (KFMAM and Elderly and Disabled medical manuals): HTTP 403
  (467-byte body, AkamaiGHost). The KEESM scope in the corpus is the DCF cash and food assistance manual.
- **us-nm** — hca.nm.gov Medical Assistance Program Manual page: HTTP 403 (986-byte body, CloudFront). The NMAC
  compilation publisher (srca.nm.gov) lists Title 8 chapters 200-299 but its chapter pages enumerate only
  reserved part ranges without links to the active parts, so no publisher index exists there either (reviewer
  judgment: not ingested by guessing part URLs).
- **us-ne** — dhhs.ne.gov Medicaid Eligibility Regulations page: no TCP answer (ConnectTimeout; curl 28 at 20 s).

### Already in corpus (done, pointers)

- **us-wv** — West Virginia BFA Income Maintenance Manual (`manifests/us-wv-manuals.yaml`, version
  `2026-07-21-wv-income-maintenance-manual`, one integrated PDF effective 2026-07-01, 2,276 page provisions, 923
  of them mentioning Medicaid) carries the Medicaid eligibility chapters alongside SNAP and WV WORKS. Pulled as
  the sixteenth state, found covered by the first agent.
- **us-id** — Idaho publishes no separate Medicaid eligibility manual; eligibility is IDAPA 16.03.01 (Medicaid
  for families and children) and 16.03.05 (AABD) on the Office of the Administrative Rules Coordinator site
  (current-rules listing: 21 Title 16 rule PDFs, 2 of them the eligibility chapters). The first agent generated
  a two-document manifest for them at page granularity. This session found both chapters already in the corpus
  at section granularity as `regulation`: `us-id/regulation/idapa/16/03/05` (`manifests/us-id-aabd-rules.yaml`,
  version `2026-07-04-id-aabd-rules`, 286 provisions, coverage complete, committed) and
  `us-id/regulation/idapa/16/03/01` (today's CHIP batch, version `2026-09-10-chip-state-eligibility-manual`, 75
  provisions, coverage complete, unsigned and uncommitted). Reviewer judgment: total coverage of the target
  documents in a better granularity is the IL/WV `done` case, not the batch-2 partial-overlap case, so the
  manifest was removed, `build_id()` dropped from the generator and the row rewritten as `done` with pointers.
  If the controller does not publish the CHIP scope, 16.03.01 is the gap to close for ID. Does not count toward
  the batch.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-medicaid-state-eligibility-manual.json`

for xx in ok, ct, ia, nv, ms, under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` (main checkout), alongside
the batch-1 and batch-2 artifacts. The OK artifacts were deleted and rebuilt once after the manifest grew from
250 to 350 documents, so no stale source files remain from the first run.

Rebuild:

```bash
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 3
for j in ok ct ia nv ms; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-medicaid-state-eligibility-manual \
    --manifest manifests/us-$j-medicaid-eligibility-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

Lint: `uv run ruff check scripts/build_medicaid_state_eligibility_manual_manifests.py` is clean.
`uv run ruff check scripts/` still reports the 8 pre-existing findings in
`scripts/build_liheap_state_plan_manifests.py` and `scripts/draft_program_work_orders.py` noted in batch 2; left
alone (reviewer judgment, unchanged).

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped (39 s; run after every change in this session). The 10 failures are exactly the expected pre-existing data-dependent tests of this sparse
worktree (`test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` x2,
`test_rulespec_be_source_promotion`, `test_us_ak/ct/mi/mt/nd/ny_snap_manual`); none touches the Medicaid
manifests or the generator, and no other test failed.

## Reviewer judgments (all of them)

1. Continuation: the first agent's sixteen queue rows, blocked-row failure texts and five of its six manifests
   were kept as found on disk (verified against the generator and the publishers' indexes only where noted);
   the blocked publishers were not re-probed.
2. Probe cap: sixteen states probed, five attempted; the ten-attempted target is not reachable within the cap
   and no seventeenth state was pulled.
3. ID: recorded `done` with pointers to the two existing `us-id/regulation` scopes instead of re-ingesting both
   IDAPA chapters as `manual` at page granularity; the first agent's manifest and `build_id()` were removed; the
   dependency on the unsigned CHIP scope for 16.03.01 is recorded.
4. OK: the 100 title-only or "35-x-y."-labelled sections were being dropped silently; numbering is now read from
   each section page (0 disagreements with the "SECTION n" labels the first agent relied on), all 350 sections
   are taken, the two publisher numbering duplicates are kept with slug suffixes, subchapter and part landing
   pages are not taken, and OHCA's own web publication is the source although its footer defers to the SOS OAC
   (the codified-rules-as-`manual` judgment of MA, CO and NJ applies; the controller may prefer `regulation`).
5. CT: the entire UPM (ten chapters, cash programs included) is the Medicaid manual because the manual is
   integrated section by section; policy transmittals not taken; 13 sections already in the SSP policy scope
   re-fetched under Medicaid paths; legacy `.doc` conversion relies on `textutil`/`antiword`/`catdoc`.
6. IA: Title 8 chapters only; the Title 8 omnibus (same text in one file) and the other titles are not taken.
7. NV: chapters, table of contents and appendices taken; the 72 manual transmittal letters are not.
8. MS: chapters and every Appendix A item taken, including the notice and form appendices A-12 to A-16, because
   they are numbered items of the manual's own appendix.
9. PDF manuals at page granularity with OCR fallback; `expression_date` = fetch date (as batches 1 and 2).
10. Extraction runs overlapped (CT in the background throughout), so per-state seconds are shared-resource wall
    times.
11. `ruff` findings in two unrelated scripts under `scripts/` left unfixed (as batch 2).
12. The generator's `_blocked3()` placeholder idiom from the first agent (`_jur` popped in a module-level loop)
    was left as written because it lints clean and produces the intended rows.

## Remaining for later batches

States not yet attempted (by population): SC, AL, LA, KY, OR, UT, KS, NM, NE (all blocked from this network),
then HI, NH, ME, MT, RI, DE, SD, ND, AK, DC, VT, WY, plus the territories. CA, OH, AZ, TN (batches 1 and 2) and
the nine batch-3 blocks need a retry from another network or an official export. Follow-on families: CT policy
transmittals; NV manual transmittal letters; OK subchapter/part landing pages are link lists only; ID 16.03.01
if the CHIP scope is not published; the batch-1 and batch-2 lists (MO General Information and 1973 Eligibility
Requirements manuals, WI section-level pass, MD action transmittals, IN transmittals, NY GIS/ADM, TX TWH Parts
B-X, NC letters, GA MTs, 42 CFR part 436). Controller steps after review: decide `manual` vs `regulation` for
OK (and MA, CO, NJ), `sign-ingest-manifest` per scope, immutable release selector, `publish_corpus.py --dry-run`,
then publication and activation.
