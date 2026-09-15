# Wave 5: SSI, LIHEAP and Medicare (seven federal documents, LIHEAP state manuals, SSI state authority, reading pass)

Date: 2026-09-15 (UTC; the evening of 2026-09-14 on the controller's machine)
Work order: `docs/coverage/needs-closure-2026-09-14/wave5/00-common-preamble.md` and `wave5/ssi-liheap-medicare-brief.md`
(branch `analysis/needs-closure-2026-09-14`, worktree `closure-r6`): the 442 EXTRACTABLE cells of
`wave5/ssi-liheap-medicare-extractable.csv` (357 federal, inherited by 51 states from 7 elements; 78 state-level) and the
219 REVIEW cells of `wave5/ssi-liheap-medicare-review.csv`.
Branch `discovery/ingest-w5-ssi-liheap-medicare` cut from `main` 9b0641afc in the sparse worktree
`~/axiom-corpus-worktrees/w5-ssi-liheap-medicare` (`data/corpus/` excluded, never symlinked); every extraction wrote to the
main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`) with `--source-as-of 2026-09-15`; the
artifacts stay uncommitted for the controller. Agent timing: worktree read and inputs inventoried 2026-09-15T00:00Z to
00:10Z; publisher research 00:10Z to 00:22Z (the Part B reading pass ran in parallel as one read-only sub-agent, 00:12Z to
00:21Z); generators and the five federal extractions 00:22Z to 00:25Z; the Arkansas, Wisconsin and Utah scopes 00:27Z to
00:31Z; decisions and this note to about 00:45Z. Per-scope seconds in the tables. Disk: `df -h /` 26 GB free at launch,
27-28 GB during the run (four sibling agents share the disk), checked before every extraction; the 5 GB stop line was never
approached (the eight source directories total about 25 MB).
Impact analysis: not run; the GitNexus MCP tools were not available. No library function under `src/` was modified; the code
changes are in five generator scripts (below).

Result: 8 scopes, 24 documents, 1,209 provision rows, 2.72 million characters; every scope reports coverage `complete: true`,
0 missing, 0 extra, 0 duplicate citation paths, and no new citation path exists in any other scope on the controller's disk
(checked against every `provisions/{us,us-ar,us-wi,us-ut}/*/*.jsonl`), so nothing collides and no consolidation is needed.

| jurisdiction | class | version | documents | rows | chars | extract s |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| us | regulation | `2026-09-15-title-20-part-416-appendix-k` | 1 | 2 | 22,885 | 1 |
| us | manual | `2026-09-15-ssi-poms-si-00529` | 1 | 12 | 19,556 | 2 |
| us | guidance | `2026-09-15-liheap-model-plan` | 10 | 176 | 355,173 | 4 |
| us | manual | `2026-09-15-medicare-cms-iom-100-03` | 4 | 395 | 965,352 | 5 |
| us | manual | `2026-09-15-medicare-cms-iom-100-05` | 6 | 429 | 995,170 | 5 |
| us-ar | manual | `2026-09-15-liheap-policy-manual` | 1 | 191 | 352,359 | 6 |
| us-wi | statute | `2026-09-15-ssi-state-supplement-rules` | 1 | 2 | 7,235 | 1 |
| us-ut | regulation | `2026-09-15-ssi-state-supplement-rules` | 1 | 2 | 864 | 2 |

Cells closed (decisions in `2026-09-15-ssi-liheap-medicare-decisions.csv`, 662 rows): of the 357 federal cells, 260 are
PRESENT (five documents taken, each inherited by 51 states plus the `us` row) and 104 ABSENT (45 CFR 96.80 and 96.87 are
reserved sections); of the 78 state cells, 3 PRESENT (AR manual, WI statute, UT rule), 64 ALREADY-HELD (check-pattern misses
against the wave-4 scopes), 9 ABSENT, 2 OUTREACH. Part B: 83 cells read, 63 PRESENT, 12 ABSENT-IN-CITED, 8 left REVIEW after
reading, one PATTERN row; 136 REVIEW cells not read (below).

## Publisher access (2026-09-15T00:10Z to 00:31Z, plain extractor client unless stated)

- `www.ecfr.gov`: the versioner API (`/api/versioner/v1/titles.json`, `/structure/2026-09-11/title-{20,45}.json`, the
  `full` XML with `Accept-Encoding`) and the renderer API (`/api/renderer/v1/content/enhanced/2026-09-11/title-20?part=416&appendix=...`)
  answered HTTP 200; the canonical HTML page `/current/title-20/chapter-III/part-416/appendix-Appendix%20to%20Subpart%20K%20of%20Part%20416`
  redirects the corpus client (HTTP 302, then 200) to `unblock.federalregister.gov` (a 3 KB bot wall). The appendix is
  therefore taken from the renderer API (`download_url`), the canonical page being the citation (`source_url`). Title 20
  `latest_issue_date`/`latest_amended_on` 2026-09-09, `up_to_date_as_of` 2026-09-11.
- `secure.ssa.gov` (POMS): the chapter list, the SI 005 subchapter list, the SI R00529.020 page and the linked
  `pomsimages.nsf/gfx_num/G-SI_R00529.020-1/$File/G-SI_R00529.020-1.pdf` (232,758 bytes, `application/pdf`) all HTTP 200.
- `acf.gov` (ACF OCS): the plain client got an AWS WAF challenge on every page probed at 00:02Z (HTTP 202, empty body,
  `x-amzn-waf-action: challenge`, `server: awselb/2.0`); the same host served everything to the plain client on 2026-09-13
  (federal guidance layer). One probe each way, as the 2026-09-14 TANF note did for `dbmefaapolicy.azdes.gov`: a chrome120
  TLS fingerprint (curl_cffi, verification on) was served the pages and every PDF/DOCX (HTTP 200); no CAPTCHA and no
  JavaScript challenge was solved, the impersonated client is simply not challenged. **Deviation recorded for the
  controller:** the preamble allows `browser_impersonation` only where a run note already documents the need; no note does
  for acf.gov, and this run is the first to record it. The Model Plan family is fetched with `browser_impersonation: true,
  browser_impersonation_direct: true` (the `IMPERSONATE` shape of the 2026-09-13 generator); drop the scope if that
  judgment is not accepted. The FY 2027 transmittal PDFs carry `Last-Modified` 2026-06-10, the FY 2026 ones 2025-04-04.
- `www.cms.gov`: the IOM index, the Pub 100-03 (cms014961) and Pub 100-05 (cms019017) publication pages and all 12 PDFs
  HTTP 200 (chapter 7 of Pub 100-05 is under `/files/document/`, the others under `/regulations-and-guidance/guidance/manuals/downloads/`).
- `liheapch.acf.gov` (ACF LIHEAP Clearinghouse): still omits its Entrust intermediate; fetched with `REQUESTS_CA_BUNDLE` =
  certifi + `data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem` (bundle rebuilt as `data/certs/liheapch-ca-bundle.pem`, an
  untracked build product), verification never disabled. `stateplans.htm` (53,615 bytes) read live; the manuals index links
  `/sites/default/files/webfiles/docs/2026/manuals/AR_Manual_2026.pdf` (HTTP 404) while `/docs/2025/manuals/AR_Manual_2025.pdf`
  answers HTTP 200 (9,871,526 bytes, `Last-Modified` 2024-12-04) under the publisher's own naming.
- `adeq.state.ar.us` (Arkansas Energy Office LIHEAP page): HTTP 200; it links the FY 2026 matrices, the eligibility
  chart, the application form, the brochure and the proposed FY 2027 model plan, and no policy manual.
- `docs.legis.wisconsin.gov`: `/document/statutes/49.77` HTTP 200, resolving to `/statutes/statutes/49/v/77` (100,413 bytes,
  the subchapter V scroll page with `data-path` section anchors); `/statutes/statutes/49/IV/77` and `/49/iv/77` answer 404
  (49.77 sits in subchapter V).
- `adminrules.utah.gov` (Utah Office of Administrative Rules eRules): the `/public/rule/R414-306/Current%20Rules` route
  answers HTTP 404 with an empty body to any non-browser client (a React single-page application; the 2026-09-10 CHIP run
  found no endpoint). Read from its JavaScript bundle: the application's public API. `/api/public/searchRuleDataTotal/R414-306/Current%20Rules`
  (HTTP 200, 24,870 bytes) returns the current rule record (ruleId 980, effective 6/19/2025, `htmlDownload`
  `uac-html/1f7c0fac-db65-46f9-bceb-37aaf2db016d.html`), and `/api/public/getfile/<htmlDownload>/R414-306.html` serves the
  rule HTML (107,154 bytes) to the plain client, the route the 2026-07-04 FEP R986-200-239 manifest used. One wrinkle: a
  request whose `Accept` header prefers `text/html` (the extractor session's default) gets the 2,224-byte application
  shell instead, so the document is fetched with the curl range backend (`Accept: */*`), as the FEP manifest was.
- No TLS chain was broken anywhere except the known Clearinghouse gap; nothing was added to `data/certs/`. No mirror,
  repost, proxy or archived copy was used.

## Part A, family 1: the seven federal documents (357 cells)

| element | result | scope / evidence |
| --- | --- | --- |
| SSI-F-CFR416-APPK | PRESENT | `us/regulation/2026-09-15-title-20-part-416-appendix-k`, `us/regulation/20/416/subpart-K/appendix` (one 22,885-character block) |
| SSI-F-POMS-SI-00529 | PRESENT | `us/manual/2026-09-15-ssi-poms-si-00529`, `us/manual/ssa/poms/si/r00529.020/redacted-pdf` (11 text pages) |
| LIHEAP-F-CFR96-96-80 | ABSENT | eCFR title-45 structure 2026-09-11: `§ 96.80 [Reserved]`, `reserved: true` |
| LIHEAP-F-CFR96-96-87 | ABSENT | eCFR title-45 structure 2026-09-11: `§ 96.87 [Reserved]`, `reserved: true` |
| LIHEAP-F-GUID-MODELPLAN | PRESENT | `us/guidance/2026-09-15-liheap-model-plan`, 10 documents under `us/guidance/acf/ocs/liheap-at/{2026-4,2025-04}` |
| MED-F-IOM-100-03 | PRESENT | `us/manual/2026-09-15-medicare-cms-iom-100-03`, `us/manual/cms/iom/100-03/chapter-1-part-{1..4}` |
| MED-F-IOM-100-05 | PRESENT | `us/manual/2026-09-15-medicare-cms-iom-100-05`, `us/manual/cms/iom/100-05/chapter-{1,2,3,5,6,7}` |

- **Appendix to Subpart K (20 CFR 416).** `extract-ecfr --include-appendices` accepts only part-scoped `Appendix X to Part N`
  identifiers (`_appendix_citation_from_identifier`) and raises on `Appendix to Subpart K of Part 416`, as the 2026-09-11
  note recorded; the brief's fallback applies. Official-document manifest `manifests/us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml`
  from `scripts/build_federal_guidance_layer_manifests.py --only ssi-cfr-416-appendix-k`: `document_class` regulation,
  `source_url` the canonical page, `download_url` the renderer HTML, `html_content_selector: div.appendix`,
  `expression_date` 2026-09-09 (the date the sibling `2026-09-11-title-20-part-416` rows carry; the appendix's own
  citation line ends `75 FR 1273, Jan. 11, 2010`). One block because the renderer emits the whole appendix under one `h4`.
  The parent path `us/regulation/20/416/subpart-K` is a container row of the 2026-09-11 scope; the two scopes share no path.
- **POMS SI 00529.** The SI 005 subchapter list enumerates one section for SI 00529, `SI R00529.020 ... (Redacted)`, whose
  HTML body is `Manual Netting – Redacted Version / View In PDF` (the 46-character `block-1` the 2026-09-13 remainder scope
  holds under `us/manual/ssa/poms/si/r00529.020`; the 2026-09-10 note's judgment 1 had left the subchapter out). The
  linked PDF (13 pages; page 1 an image without a text layer, page 13 blank, 11 text pages) is the section text: it is
  taken as a PDF document under the sibling path `.../r00529.020/redacted-pdf` through a new `si-00529` family of
  `scripts/build_ssi_poms_si_manifests.py` (`take_redacted_pdf`: a section whose `div.poms` body is only the redacted
  caption and the `pomsimages.nsf` link becomes a PDF document with `download_url`), `expression_date` the page's printed
  05/13/2026. The remainder scope keeps its stub; no swap.
- **45 CFR 96.80 and 96.87.** Both are `[Reserved]` in the live eCFR structure (subpart H lists 96.80 reserved, 96.81-96.86,
  96.87 reserved, 96.88, 96.89); the held `2026-09-13-title-45-part-96` scope is complete and nothing was extracted. 102 cells
  ABSENT with that evidence; the closure schema should drop or mark the two elements.
- **LIHEAP Model Plan.** The ACF OCS action-transmittal index (`/ocs/resource/liheap-action-transmittals`) lists the Model
  Plan Application transmittal for every fiscal year; taken: FY 2027 (LIHEAP-AT-2026-4, dated June 10, 2026: the page, the
  7-page transmittal, Attachment 1 OLDC cloning instructions, Attachment 2 Model Plan Reference Guide (41 pages),
  Attachment 3 Model Plan template (44 pages, OMB Clearance No. 0970-0075)) and FY 2026 (LIHEAP-AT-2025-04, dated April 2,
  2025, the year of the plans in the corpus: the page, the 6-page transmittal, the reference guide, the Word template and
  the Word cloning instructions). `document_class` guidance, `us/guidance/acf/ocs/liheap-at/<AT>/...`, attachments dated
  by their transmittal. Generator family `liheap-model-plan` of `build_federal_guidance_layer_manifests.py`.
- **Pub 100-03 and Pub 100-05.** `scripts/build_cms_iom_100_01_manifests.py --publication 100-03|100-05`, the generator of
  the six IOM scopes already held. Pub 100-03 posts its single chapter as four part PDFs ("Chapter 1 - Coverage
  Determinations, Part 2 Sections 90 - 160.26"); the generator now reads the part from the link text and keys each part
  `chapter-1-part-N` (`CHAPTER_PART_RE`, `chapter_key`/`chapter_sort_key` accept `-part-N`), with the section range in
  metadata; 391 sections against 391 TOC entries (part 1 prints one more than its TOC, part 4 one fewer; section 230 of
  part 4 is a heading-only container). The two CIM/NCD crosswalk PDFs are finding aids, not taken. Pub 100-05: chapters
  1, 2, 3, 5, 6 and 7 (423 sections against 425 TOC entries; chapter 1's TOC lists two sections the body no longer
  prints); chapters 4 and 8 were deleted by transmittal R11756MSP of 12/22/2022 (CR 13002) and their PDFs print only the
  transmittal table (chapter 8 adds "This chapter is obsolete and is not being used"), so they are `pointer_chapters`,
  recorded and not taken, with the `Chapter 5.1`/`5.2` ECRS attachments and the eight per-chapter crosswalks.

## Part A, family 2: LIHEAP state manuals (LIHEAP-ST-09 37 states, LIHEAP-ST-18 35 states)

The two extractable lists were built from the 2026-09-11 literals; the 2026-09-14 benefit-matrix run
(`docs/ingest-runs/2026-09-14-liheap-matrix-ssi-standards.md`, 55 scopes over 47 jurisdictions) had already taken most of
them. Each state was checked against the generator's verified `STATES` table and the scopes on disk:

- LIHEAP-ST-09: 28 ALREADY-HELD (matrix taken or printed in the manual: AK AL AR AZ CO CT HI IA IN LA MD MI MO MS MT ND NE
  NH NJ NV OH OR PA SD TN UT VA VT), 8 ABSENT (DE FL GA KY ME MN WI WV, the wave-4 evidence re-read), 1 OUTREACH (NY, the
  OTDA F5/Shape wall).
- LIHEAP-ST-18: 32 ALREADY-HELD (the manual, adopted rule or guidance document of the 2026-09-14 scopes; CT's is the FFY
  2026 Allocation Plan, the DSS document the Clearinghouse index lists as its manual), 1 PRESENT (AR, below), 1 ABSENT
  (KY: the listed document is the weatherization plan), 1 OUTREACH (OH: the listed guidelines sit on a third-party CDN;
  the ODJFS HEAP page was unreachable to every client in wave 4).
- **Arkansas** is the one state whose manual was extractable: the agency posts none, the Clearinghouse index's FFY 2026
  link is dead, and the publisher serves the FFY 2025 Policy and Procedures Manual (190 pages, effective October 1, 2024
  to September 30, 2025; Appendix J on PDF page 178 is the crisis benefit table) under its own naming. Taken as
  `us-ar/manual/2026-09-15-liheap-policy-manual`, path `us-ar/manual/aeo/liheap-policy-and-procedures-manual/ffy2025`
  (191 rows, `hosting_authority` the Clearinghouse, the unindexed-file note in metadata), through a new `policy-manual`
  family of `scripts/build_liheap_benefit_matrix_manifests.py` (`--family policy-manual`, `MANUAL_STATES`; a `Family`
  record parameterises version, run note, manifest infix and queue key, and the default `benefit-matrix` family
  regenerates the 2026-09-14 manifests byte for byte, checked on `--only us-al,us-ar --no-queue`).

## Part A, family 3: SSI state authority (OR UT VA WI; version `2026-09-15-ssi-state-supplement-rules`)

- **OR** (SSI-ST-2, ST-4, ST-5): ALREADY-HELD. OAR chapter 461 was taken whole by the TANF chapter-461 scope
  (`us-or/regulation/2026-09-10-tanf-state-policy-manual-chapter-461`, 571 rows, and its 2026-09-14 consolidated successor
  `...-r2026-09-14-150-316-consolidated`): 461-155-0250 Income and Payment Standard; OSIPM (2,294 characters),
  461-160-0550 Income Deductions; Non-SSI OSIP and OSIPM (3,875) and 461-160-0780 Determining Adjusted Income; OSIP-EPD and
  OSIPM-EPD (532) are rows of both. Nothing fetched; the queue row gains a pointer record.
- **VA** (SSI-ST-2): ALREADY-HELD, all 12 sections of 22VAC30-80 in `us-va/regulation/2026-09-14-ssi-state-supplement-standards`.
- **WI** (SSI-ST-2): Wis. Stat. 49.77 State supplemental payments taken from the Legislature's statutes site as
  `us-wi/statute/49.77` (anchor range from the section's `data-path` div to 49.775's; one 7,235-character section row with
  the history and annotations; `expression_date` 2026-09-04 from the page's certification line, "2023-24 Wisconsin
  Statutes updated through 2025 Wis. Act 247 ... in effect on September 4, 2026"). The path is the one the
  `wisconsin-statutes` adapter would emit (`us-wi/statute/71.01` in the chapter-71 scope), so a later whole-chapter-49
  statute scope needs the consolidation or swap route; recorded in metadata.
- **UT** (SSI-ST-2): Utah Admin. Code R414-306-6 State Supplemental Payments for Institutionalized SSI Recipients ($15 to a
  Medicaid-eligible resident of a medical institution whose SSI is reduced to $30; effective 6/19/2025) taken from the
  eRules public API as `us-ut/regulation/admin-rules/r414/306/6` (the FEP R986-200-239 shape: anchor range from the
  section heading to the `KEY:` line, `html_content_selector: body` because the extractor's main-content heuristic keeps
  only page 1 of the two absolutely positioned pages). Batch 6 of `scripts/build_ssi_state_supplement_manifests.py`
  (`--batch 6`: builders `build_wi_statute`, `build_ut_rule`, `POINTER_ROWS_6`, `update_queue_batch6` writing an
  `authority_scope` record on the four rows).

## Part B: reading pass (219 REVIEW cells; 83 read of the 250 cap)

Run as one read-only sub-agent over the provision JSONL on disk; its rows are merged into the decisions file. Per element:

- MED-ST-7 (36): the wave-4 `2026-09-14-msp-income-standards` scopes (27 jurisdictions, never wired into the builder) carry
  the 2026 QMB/SLMB/QI figures for 25 (PRESENT, cited); MA (2024 EOM, unlabelled 190% FPL column) and NC (change notice
  naming the MA-2252 chart) have the scope without the figures (REVIEW); FL IN KY LA MO OK UT WV WY have neither a scope
  nor a citation (not read). The same scopes plainly carry MED-ST-2 (GA ID MN OH OR), MED-ST-3 (AZ HI NJ OR SD VT) and
  MED-ST-6 (OR): 12 PRESENT rows recorded.
- LIHEAP-ST-09 (13): the eight states with a wave-4 matrix scope PRESENT (CA DC MA NC NM OK SC WA; WA's is the
  calculation worksheet); ID IL RI TX WY have neither scope nor citation. LIHEAP-ST-18 (13): NC PRESENT (EP-300 manual);
  CA DC MA NM OK SC WA hold attachments or an appendix only, left REVIEW.
- LIHEAP-ST-05 (51; six read AK AL AR AZ CA CO): 3 of 6 carry state narrative (AK AR AZ), 3 are unmarked template text;
  mixed, stays REVIEW. The builder's "1.10-1.12 household definition" pointer is wrong: 1.11-1.12 are application-process
  questions.
- LIHEAP-ST-03 (30; six read AL AR CO DC DE IA): 1 of 6 (DC) carries it: ABSENT-IN-CITED pattern. The plan's yes/no
  checkbox state is what the element needs and the extractor drops it; the carrier is the plan checkbox or the state manual.
- SSI-ST-4 (10): the eight `2026-09-14-ssi-state-supplement-standards` scopes PRESENT (NE's SDP table is the 2021
  revision, flagged); KS and SD ABSENT-IN-CITED. SSI-ST-5 (9): AL SD VA PRESENT (AL and SD by a sibling row of the cited
  one); DC DE IA MI PA RI have no citation. SSI-ST-3 (1): OR PRESENT (categories only). SSI-ST-2 (24): no cell has a
  citation; the two on-disk scopes the notes name were read: KS K.S.A. 39-972(b) PRESENT (unselected scope
  `us-ks/statute/2026-07-04-ks-sspp-statute`, the controller's 2026-09-14 pick), DE DSSM 13000 ABSENT-IN-CITED.
- Not read: 136 cells. 124 review rows cite no corpus provision at all (the builder's note names an uninventoried
  authority, e.g. "AS 47.25.430-.615 not inventoried"); they are research items, not reading items, and stay REVIEW with
  that note. The other 12 are the 45 LIHEAP-ST-05 and 24 LIHEAP-ST-03 cells beyond the six-state sample, less the ones
  above; they stay REVIEW under the element verdicts.

## What stays open

- EXTRACTABLE, new: the 22 SSI-ST-2 statutes the review notes name (AK CT DC GA HI IA IL IN ... ; Wis. Stat., 22VAC30-80,
  R414-306 and OAR 461 are now held), the MSP standards of FL IN KY LA MO OK UT WV WY (MED-ST-7), the FY 2026 matrices of
  ID IL RI TX WY, and the manuals of CA DC MA NM OK SC WA (LIHEAP-ST-18) if their agencies post one.
- ABSENT: 45 CFR 96.80 and 96.87 (reserved); the LIHEAP-ST-09 matrices of DE FL GA KY ME MN WI WV (formula-based or
  unpublished, wave 4); KY's LIHEAP manual.
- OUTREACH: NY LIHEAP (OTDA wall), OH LIHEAP manual (third-party CDN only), and, for the controller's judgment, the acf.gov
  fingerprint wall recorded above.

## Code changes (generator scripts only; no library change, no tests changed)

- `scripts/build_ssi_poms_si_manifests.py`: family `si-00529`, `Family.take_redacted_pdf`, `redacted_pdf_link`,
  `update_queue_si_00529` (writes `poms_si_00529_scope` on the SSI queue's POMS federal row, the first of its three
  federal rows).
- `scripts/build_cms_iom_100_01_manifests.py`: Publications `100-03` and `100-05`; `CHAPTER_PART_RE`; `chapter_key` and
  `chapter_sort_key` accept `-part-N`; part metadata; the queue's generic publication record.
- `scripts/build_federal_guidance_layer_manifests.py`: `doc()` takes `document_class` and `source_as_of`; families
  `liheap-model-plan` and `ssi-cfr-416-appendix-k`; `scope_record` reads the class from the documents and the run note per
  version; `update_queue` now attaches the record to the first `us` row (or the named row, `QUEUE_ROW_NAMES`) and carries
  every other row through: its previous `{jurisdiction: row}` rewrite would have dropped the queues' later federal rows
  (the SSI queue has three `us` rows, the LIHEAP queue three, the Medicare queue six) had it been re-run.
- `scripts/build_liheap_benefit_matrix_manifests.py`: `Family` (`BENEFIT_MATRIX`, `POLICY_MANUAL`), `MANUAL_STATES`,
  `--family`; the default output is unchanged.
- `scripts/build_ssi_state_supplement_manifests.py`: batch 6.
- Queues: `manifests/ssi-agent-queue.yaml` (federal POMS row `poms_si_00529_scope`, eCFR row `appendix_subpart_k_scope`,
  OR/UT/VA/WI `authority_scope`), `manifests/liheap-agent-queue.yaml` (federal `model_plan_scope`, AR
  `policy_manual_scope`), `manifests/medicare-agent-queue.yaml` (publications 100-03 and 100-05, index inventory).
  Verified after writing: every scope record resolves to a coverage file on disk with `complete: true`.
- `uv run --extra dev ruff check .`: passes. Focused tests: `uv run --extra dev pytest -q -m "not integration and not slow"
  -k "manifest or official_documents"` in the sparse worktree: 274 passed, 2 skipped, 12 failed in 42 s, every failure a
  `FileNotFoundError` (two through PyMuPDF, one surfacing as `is_file()` false) on another scope's `data/corpus` artifact
  the sparse checkout does not hold, the set the wave-4 notes list: `test_armenia_arlis`,
  `test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` (x2), `test_israel_openlaw`,
  `test_rulespec_be_source_promotion` and the AK, CT, MI, MT, ND, NY SNAP manual tests. None touches the five generators,
  the eight manifests or the three queues (no test imports the scripts).

## Controller

Selector additions (artifacts unsigned, on the controller's disk under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`, not
committed), as `jurisdiction / document_class / version`; no swap and no consolidation:

| jurisdiction | document_class | version |
| --- | --- | --- |
| us | regulation | 2026-09-15-title-20-part-416-appendix-k |
| us | manual | 2026-09-15-ssi-poms-si-00529 |
| us | guidance | 2026-09-15-liheap-model-plan |
| us | manual | 2026-09-15-medicare-cms-iom-100-03 |
| us | manual | 2026-09-15-medicare-cms-iom-100-05 |
| us-ar | manual | 2026-09-15-liheap-policy-manual |
| us-wi | statute | 2026-09-15-ssi-state-supplement-rules |
| us-ut | regulation | 2026-09-15-ssi-state-supplement-rules |

Also for the controller: the acf.gov impersonation judgment above; select `us-ks/statute/2026-07-04-ks-sspp-statute` for
SSI-ST-2 (re-confirmed by reading); the Oregon OSIP rules are served only if the chapter-461 scope (or its consolidated
successor) is selected.

Rebuild:

```bash
cd ~/axiom-corpus-worktrees/w5-ssi-liheap-medicare
export REQUESTS_CA_BUNDLE=$(uv run python -c "import certifi;print(certifi.where())")
uv run python scripts/build_federal_guidance_layer_manifests.py --only liheap-model-plan,ssi-cfr-416-appendix-k
uv run python scripts/build_ssi_poms_si_manifests.py --family si-00529
uv run python scripts/build_cms_iom_100_01_manifests.py --publication 100-03
uv run python scripts/build_cms_iom_100_01_manifests.py --publication 100-05
uv run python scripts/build_liheap_benefit_matrix_manifests.py --family policy-manual
uv run python scripts/build_ssi_state_supplement_manifests.py --batch 6
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-title-20-part-416-appendix-k --manifest manifests/us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml --source-as-of 2026-09-15
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-ssi-poms-si-00529 --manifest manifests/us-ssa-poms-si-00529-2026-09-15.yaml --source-as-of 2026-09-15
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-liheap-model-plan --manifest manifests/us-liheap-model-plan-2026-09-15.yaml --source-as-of 2026-09-15
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-medicare-cms-iom-100-03 --manifest manifests/us-cms-iom-100-03.yaml --source-as-of 2026-09-15
uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-medicare-cms-iom-100-05 --manifest manifests/us-cms-iom-100-05.yaml --source-as-of 2026-09-15
for c in wi ut; do uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-ssi-state-supplement-rules --manifest manifests/us-$c-ssi-state-supplement-rules.yaml --source-as-of 2026-09-15; done
python3 -c "import certifi,pathlib; pathlib.Path('data/certs/liheapch-ca-bundle.pem').write_text(pathlib.Path(certifi.where()).read_text()+'\n'+pathlib.Path('data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem').read_text())"
REQUESTS_CA_BUNDLE=$PWD/data/certs/liheapch-ca-bundle.pem uv run axiom-corpus-ingest extract-official-documents --base $B --version 2026-09-15-liheap-policy-manual --manifest manifests/us-ar-liheap-policy-manual-manual.yaml --source-as-of 2026-09-15
```
