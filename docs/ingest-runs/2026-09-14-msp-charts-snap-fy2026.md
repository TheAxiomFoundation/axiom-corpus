# State chart families: Medicare Savings Program income/resource standards (36 states) and SNAP FY 2026 state transmittals (25 states)

Date: 2026-09-14
Work order: the two state-level chart families the needs-driven closure check left open
(`docs/coverage/needs-closure-2026-09-11/medicare.md` MED-ST-7 with MED-ST-2/3/4 where the chart carries them, 36 states;
`snap.md` snap_s20, the 25 states whose cell is not PRESENT in `snap-matrix.csv`).
Branch `discovery/ingest-msp-charts-snap-fy2026` cut from `origin/main` (5c2505ec6) in the sparse worktree
`~/axiom-corpus-worktrees/msp-snap-charts` (`data/corpus/` excluded, never symlinked); every extraction wrote to the main
checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`, `--source-as-of 2026-09-14`).
Impact analysis: no library function was modified (the GitNexus tools were not needed); the code change is two new
generator modules, `scripts/build_msp_snap_state_charts_manifests.py` and `scripts/msp_snap_state_chart_records.py`.
Disk: `df -g ~` 33 GB free at start, 30 GB at the end (stop line 5 GB never approached).

Discovery: seven read-only discovery agents (four for MSP, three for SNAP) located each state's document on the
publisher's own site, probed it from this machine with the plain corpus client and, on 403/reset, once with the
extractor's `browser_impersonation` client, read the figures and wrote an evidence record per state; the records module
carries the result verbatim (URL, dates, figures, host behaviour). Every found document was then checked against the
main checkout's corpus (inventory URLs and provision bodies of every scope of the jurisdiction) before a manifest was
written: where the same edition is already held in a selected scope the state is closed by pointer and nothing is
re-taken (ten states, listed per family below).

Result: 49 new scopes (27 MSP, 22 SNAP), 63 documents, 483 provision rows; every scope reports coverage `complete: true`,
0 missing, 0 extra, 0 duplicate citation paths, and every document carries text in at least one row (checked over the
JSONL). No `ocr: true` was needed (every PDF has a text layer). Ten states closed by pointer to a selected scope, one
blocked publisher (NY OTDA), two needs-review without a manifest (UT, WY), three partial closures with a manifest
(SD, ID, NJ SNAP).

| Family | Scopes | Documents | Provision rows | Extract s (sum) |
| --- | ---: | ---: | ---: | ---: |
| MSP income/resource standards (`2026-09-14-msp-income-standards`) | 27 | 38 | 245 | 38 |
| SNAP FY 2026 state transmittal (`2026-09-14-snap-fy2026-state-transmittal`) | 22 | 25 | 238 | 32 |

## Publisher access (2026-09-14)

- Plain corpus client (HTTP 200): azahcccs.gov, portal.ct.gov, dhcf.dc.gov, dhss.delaware.gov, medicaid.georgia.gov
  (the dch/dfcs.georgia.gov block was not involved), medquest.hawaii.gov, healthandwelfare.idaho.gov, maine.gov,
  mdhhs-pres-prod.michigan.gov, edocs.dhs.state.mn.us, dssmanuals.mo.gov (the dss.mo.gov block was not involved),
  medicaid.ms.gov, policies.ncdhhs.gov, nj.gov, hca.nm.gov, dss.nv.gov, dam.assets.ohio.gov, oregon.gov,
  secure.sos.state.or.us, eohhs.ri.gov, scdhhs.gov, dss.sd.gov, dvha.vermont.gov, hca.wa.gov, dhr.alabama.gov,
  dhs.dc.gov, humanservices.hawaii.gov, hhs.iowa.gov, content.dcf.ks.gov, mdhs.ms.gov, dhhs.ne.gov, nd.gov,
  dhs.ri.gov, tn.gov, jobs.utah.gov, ahsnet.ahs.state.vt.us.
- `browser_impersonation` (HTTP 403 or reset to the plain client, 200 to curl_cffi chrome120): hcpf.colorado.gov
  (CloudFront), kancare.ks.gov (Akamai), mass.gov (both MassHealth and DTA documents), dhhs.nh.gov (Akamai; both the
  MSP and the SNAP service release), health.ny.gov (CloudFront), dhs.state.mn.us (Radware; the Combined Manual PDF).
  ldh.la.gov's manual index answers 403 to the plain client but its PDFs answer 200 (pointer state; nothing fetched).
- Blocked (probed once plain, once impersonated, not fought): otda.ny.gov (GIS 25 TA/DC059, the FY 2026 SNAP
  standards: connection reset, then an HTTP 200 JavaScript challenge page with a support ID). Unreachable and not
  needed: hcopub.dhs.state.mn.us (EPM Appendix F; connection reset / self-signed chain), fsdimresources.mo.gov
  (Incapsula 403 to both clients), sharedsystems.dhsoha.state.or.us (incomplete TLS chain; the brochure was not needed
  because the OARs are held), the ODM MEPL index page and the ODJFS eManuals FACT index (index counts left null).
- Image-only: ecom.wyo.gov (Wyoming EOM on Google Sites) answers HTTP 200 but its dollar tables are JPEGs on
  lh3.googleusercontent.com; the extractor has no image adapter and OCR at the served 1280 px leaves the one- and
  two-person rows illegible, so Wyoming is `needs_review` without a manifest.
- TLS chains were intact on every taken host; nothing was added to `data/certs/`, no `REQUESTS_CA_BUNDLE`, never
  `verify_tls: false`. No mirror, repost, proxy or archived copy was used.

## Collisions and document classes

Every citation path was checked against every provisions JSONL of its jurisdiction under the main checkout's corpus
(all classes, all versions; the generator asserts on any overlap). Where a chart's earlier edition already has a path
(CT program standards `2026-01-01`, VT 3000 Tables) the new edition takes a dated or release-keyed sibling path
(`us-ct/policy/dss/program-standards/2026-07-01`, `us-vt/manual/dcf/3squaresvt/3100-tables-release-25-4`). Documents
already held in the same edition are pointers, not re-takes.

Document class follows the jurisdiction's precedent for the document: standalone charts, notices, memos, transmittals
and agency pages are `guidance`; documents that are part of a manual family the corpus already holds as `manual` stay
`manual` (MI RFT 242, NC change notice, NH service releases, KS KEESM appendix, ND SNAP release, UT eligibility manual
table, VT 3SquaresVT tables); the CT DSS program standards chart stays `policy`, where its January 2026 edition lives.
The draft selector `docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.selector.json` (the 2026-09-13
federal-and-plans union, 761 scopes, plus these 49) validates with `--ignore-r2-missing`: `ok: true`, 0 errors,
546 warnings, all the pre-existing `missing_parent_id` warnings.

## Family 1: MSP income and resource standards (medicare.md MED-ST-7; MED-ST-2/3/4 where carried)

Version `2026-09-14-msp-income-standards`, one scope per state, manifests `manifests/us-xx-msp-income-standards-2026.yaml`,
queue rows appended to `manifests/medicare-agent-queue.yaml` (one row per state, `closure_elements: [MED-ST-7]`,
`run_note` this file; pointer rows carry `pointer`, blocked rows `blocked_evidence`). Metadata on every document names
the extra elements the document closes (`closure_elements_extra`).

| jurisdiction | class | s | docs | rows | coverage | taken |
| --- | --- | ---: | ---: | ---: | --- | --- |
| us-az | guidance | 2 | 1 | 3 | complete | AHCCCS Eligibility Requirements chart, February 1, 2026 (QMB/SLMB/QI-1, no asset test) |
| us-co | guidance | 1 | 2 | 8 | complete | HCPF OM 26-025 (income, eff. 2026-04-01) and OM 25-078 (resources, eff. 2026-01-01); impersonation |
| us-ct | policy | 1 | 2 | 4 | complete | DSS Program Standards Chart as of 7/1/2026 (MSP eff. 3/1/2026) and the MSP eligibility page |
| us-dc | guidance | 1 | 1 | 2 | complete | DHCF QMB page (QMB only, 300% FPL + $20, no asset test; updated 2026-01-16) |
| us-de | guidance | 3 | 2 | 13 | complete | DMMA Administrative Notice A-03-2026 (eff. 2026-04-01) and the Medicaid Income Limits page |
| us-fl | pointer | | | | | Appendix A-9.1 (interim January 2026 edition) is in the selected 2026-05-27 ESS manual scope |
| us-ga | guidance | 1 | 2 | 6 | complete | 2026 Financial Limits chart (eff. 3/1/2026, rev. 3/5/2026) and 2026 Income and Resource Limits |
| us-hi | guidance | 2 | 1 | 3 | complete | 2026 MAGI and MAGI-Excepted Income Standards Chart (eff. 01/13/2026, Hawaii FPL) |
| us-id | guidance | 1 | 1 | 6 | complete | DHW Medicaid Program Income Limits page (MSP effective January 2026) |
| us-in | pointer | | | | | IHCPPM chapter 3000 (3010.35.05-.20, eff. March 1, 2026) is in the selected 2026-09-10 CHIP scope |
| us-ks | guidance | 1 | 1 | 10 | complete | KDHE Medical Assistance Standards F-8 (07-26; MSP table updated 4/1/2026); impersonation |
| us-ky | pointer | | | | | Volume IVA with MS 4455 (R. 4/13/26) is in the selected 2026-09-10 Medicaid scope |
| us-la | pointer | | | | | Z-200 (issued 2026-01-30, eff. 2026-03-01) and Z-2200 are in the selected 2026-09-10 Medicaid scope |
| us-ma | guidance | 1 | 2 | 8 | complete | EOM 24-03 (tiers 190/210/225% FPL, no asset test) and DG-FPL_2026-03 chart; impersonation |
| us-me | guidance | 1 | 1 | 7 | complete | 2026 MaineCare Eligibility Guidelines (QMB 185%, QI 250%; no SLMB tier by statute) |
| us-mi | manual | 1 | 1 | 2 | complete | RFT 242 (RFB 2026-004, 4-1-2026) from the lowercase `/olmweb/ex/` path (uppercase serves the 2025 edition) |
| us-mn | guidance | 1 | 1 | 2 | complete | DHS-3461A (6-26 edition, eff. 7/1/26), pages 1-2 as one block (pages 3-4 are the prior edition) |
| us-mo | pointer | | | | | MHABD Appendix J (07/2026) is in the selected 2026-09-10 Medicaid scope |
| us-ms | guidance | 2 | 1 | 3 | complete | Medicaid Eligibility Guide for Medicare Cost-Sharing Coverage (rev. 3/1/2026; FPL + $50 disregard) |
| us-nc | manual | 0 | 1 | 3 | complete | Change Notice 03-26 (2026 FPL changes); MA-2252 (2026) itself is in the selected 2026-09-10 scope |
| us-nh | manual | 2 | 1 | 2 | complete | SR 26-03 (03/26); MAM 601 Tables C and D are in the selected 2026-09-10 scope; impersonation |
| us-nj | guidance | 1 | 1 | 4 | complete | Medicaid Communication 26-03 (income standards eff. 1/1/2026); the DoAS MSP page is not extractable (below) |
| us-nm | guidance | 1 | 1 | 2 | complete | MAD 029 revised 04/01/2026 (the 1.1.2026 revision still carries 2025 FPL and is not taken) |
| us-nv | guidance | 0 | 1 | 2 | complete | DSS Income Limit Charts page (MAABD 2026 Medicare beneficiary limits; day of effect inferred) |
| us-ny | guidance | 1 | 3 | 15 | complete | GIS 26 MA/05, its Attachment 1 (QMB 138%, QI 186%, no resource test) and the DOH MSP page; impersonation |
| us-oh | guidance | 0 | 2 | 6 | complete | MEPL 194 (eff. 2026-03-01) and the 2026 ABD / MPAP monthly chart |
| us-ok | pointer | | | | | Appendix C-1 (7/1/2026 revision, schedules VI/VII/VII.A) is in the selected 2026-07-21 SNAP policy scope |
| us-or | guidance | 1 | 1 | 11 | complete | ODHS Help Paying Medicare Costs page; OAR 461-155-0290/-0291/-0295 (SSP 17-2026) are in the selected chapter 461 scope |
| us-ri | guidance | 1 | 1 | 4 | complete | EOHHS Medicare Premium Payment Program page (QMB 125%, QI 168%; SLMB folded into QMB 2026-02-01) |
| us-sc | guidance | 1 | 2 | 76 | complete | SCDHHS Program Eligibility and Income Limits page (eff. 03/01/2026) and the Medicaid Eligibility Programs PDF |
| us-sd | guidance | 5 | 2 | 29 | complete | partial (`needs_review`): MSP brochure EA05 (May 2026, single 135% + $20 ceiling) and the Coverage Groups page |
| us-ut | pointer | | | | | `needs_review`: TABLE II (eff. 2026-03-01) is in the selected 2026-09-10 scope but prints 100% FPL and assets only |
| us-vt | guidance | 3 | 2 | 10 | complete | 2026 MABD PIL/FPL Income Chart (eff. 4/1/2026) and 2026 Standards Change for Healthcare (v4) |
| us-wa | guidance | 1 | 1 | 4 | complete | HCA Income and Resource Standards, July 1, 2026 (MSP block 4/1/2026; WA tiers 110/120/138/200%) |
| us-wv | pointer | | | | | IMM Chapter 4 Appendix A with the 2026 figures is in the selected 2026-07-21 IMM scope (page 407) |
| us-wy | none | | | | | `needs_review`: EOM Tables 1 and 7 are JPEG images on Google Sites (no image adapter) |

State-specific tiers recorded in metadata where a name check would otherwise fail: DC (QMB only, 300% FPL), ME (QMB
185%, QI 250%, no SLMB), NY (QMB 138%, QI 186%, no SLMB), RI (QMB 125% absorbing SLMB, QI 168%), VT (QMB 150%, QI-1
202%, SLMB sunset 1/1/2026), WA (110/120/138/200%), IN (150/170/185%), CT and MA (state-set percentages), MS
(FPL + $50), NC (MQB-Q/B/E), KS (QMB/LMB/ELMB/QWD), NH (SLMB135 = QI), MI (SLM = SLMB, ALMB = QI), MO (SLMB2 = QI-1).
No-resource-test states on the charts: AZ, CT, DC, DE, ME, MS, NM, NY, OH, OR, VT, WA, MA (since 2024-03-01).

Still open in this family: WY (image tables), UT (no state document prints the 120%/135% dollar tiers), SD (no per-tier
dollars), NJ asset limits (the DoAS page nests `<main>` inside an unclosed `<nav>`, which the HTML extractor drops
before selecting content; the figures are the federal LIS limits), and the AL/CA/NE outreach states of the closure
report, which were outside this order.

## Family 2: SNAP FY 2026 state change transmittal / COLA notice (snap.md snap_s20)

Version `2026-09-14-snap-fy2026-state-transmittal`, manifests `manifests/us-xx-snap-fy2026-state-transmittal.yaml`,
queue rows appended to `manifests/snap-completion-agent-queue.yaml` (`closure_elements: [snap_s20]`).

| jurisdiction | class | s | docs | rows | coverage | taken |
| --- | --- | ---: | ---: | ---: | --- | --- |
| us-al | guidance | 1 | 1 | 5 | complete | Form DHR-FAP-1942 Summarized Eligibility Requirements (Rev. 10-25): limits, deductions, allotments |
| us-dc | guidance | 1 | 2 | 17 | complete | DHS SNAP Eligibility Requirements and SNAP Monthly Benefit pages (deduction prose still FY 2025, noted) |
| us-de | guidance | 4 | 1 | 8 | complete | DSS SNAP page table, October 1, 2025 to September 30, 2026 (limits and maximum benefits) |
| us-hi | guidance | 2 | 1 | 4 | complete | BESSD SNAP page, Hawaii gross/net standards effective 10/1/2025 (allotments not published) |
| us-ia | guidance | 1 | 2 | 32 | complete | General Letters 7-F-104 (limits, allotments eff. 10/1/25) and 7-E-126 (SUAs), 2026-02-13 |
| us-id | guidance | 1 | 1 | 9 | complete | partial (`needs_review`): Apply for SNAP page, gross limits effective October 2025 only |
| us-ks | manual | 1 | 1 | 2 | complete | KEESM Appendix F-2 FY 2026 (archived file name; the unversioned link already serves FY 2027) |
| us-ma | guidance | 1 | 1 | 52 | complete | DTA issuance tables 1-10 persons (12/16/2025); the COLA notice is in the selected 2026-08-03 scope; impersonation |
| us-mn | guidance | 5 | 1 | 20 | complete | Combined Manual Description of Changes, issued 10/2025 (page 1 watermarked DRAFT); impersonation |
| us-mo | guidance | 1 | 1 | 2 | complete | FSD flyer SNAP Changes Effective October 1, 2025 (the 2025 IM memos are password-protected) |
| us-ms | guidance | 2 | 1 | 15 | complete | MDHS SNAP page: income limits and maximum benefits effective October 1, 2025 |
| us-mt | pointer | | | | | SNAP 001 (eff. October 1, 2025) with 602-2 and 602-4 is in the selected 2026-07-17 manual scope |
| us-ne | guidance | 1 | 1 | 3 | complete | DHHS guidance document DOC00428 SNAP Program Standards effective October 1, 2025 |
| us-nh | manual | 1 | 1 | 3 | complete | SR 25-32 (10/25) October 2025 SNAP mass change, the complete figure set; impersonation |
| us-nj | guidance | 1 | 1 | 6 | complete | partial (`needs_review`): NJ SNAP eligibility page (185% gross standard, $95 minimum); no DFDI found |
| us-nm | guidance | 1 | 1 | 3 | complete | ISD 017 FPG card FY 2026 (`-final-1` revision), the complete figure set |
| us-ny | blocked | | | | | GIS 25 TA/DC059 on otda.ny.gov: JavaScript challenge to both clients (`blocked_primary_source`) |
| us-nd | manual | 1 | 1 | 7 | complete | SNAP Release 25.6 effective October 1, 2025 (the live Appendix B is already FY 2027) |
| us-oh | guidance | 0 | 1 | 5 | complete | Food Assistance Change Transmittal 105, October 1, 2025 mass change (dam.assets.ohio.gov) |
| us-or | guidance | 1 | 1 | 6 | complete | OEP-PT-25-034 FFY2026 COLA Standards for SNAP (2025-09-09) |
| us-ri | guidance | 2 | 2 | 5 | complete | SNAP Annual COLA effective October 1, 2025 and SNAP Monthly Income Guidelines FY 2026 |
| us-tn | guidance | 2 | 1 | 2 | complete | TN.gov Income Update 2026 (undated one-page chart; FY 2026 figures) |
| us-ut | manual | 1 | 1 | 3 | complete | Eligibility Manual Table 2, table effective October 1, 2025 |
| us-vt | manual | 1 | 1 | 29 | complete | 3SquaresVT Program Manual 3100 Tables, Release 25-4 (the selected 2026-07-21 scope lacks this topic) |
| us-va | pointer | | | | | Transmittal #36 is the full manual reissue held in the selected 2026-07-21 scope with the FY 2026 figures |

Still open in this family: NY (OTDA block), ID and NJ (partial), HI and MS (income limits without deductions or SUAs
on the state site), NE (the deductions guidance document DOC00429 was not located).

## Decisions

- Pointer, not re-take: a state whose current edition is already held in a selected scope gets a queue row with
  `queue_status: done`, `pointer` and `target_scope` naming that scope, and no manifest (FL, IN, KY, LA, MO, OK, WV;
  MT, VA). The closure regexes missed these because the figures sit in tables without a 2026 date next to the group
  term; the builder for the next closure check should read the pointer rows.
- Partial closures keep their manifest and are marked `needs_review` on the queue (SD, ID SNAP, NJ SNAP); UT and WY
  are `needs_review` without a manifest; NY SNAP is `blocked_primary_source` with the probe evidence.
- Multi-edition files: MN DHS-3461A stacks two editions, so pages 1-2 are one `single_block` provision; LA Z-200
  (seven yearly pages) was already held and is not re-taken.
- The MA issuance table for 11-20 persons (101 pages) and the superseded NM ISD 017 revision are recorded and not taken.
- Expression dates come from the documents (effective dates, issue dates, page-updated stamps); where a chart prints
  no date (TN, NV, OH ABD chart) the metadata names the source of the recorded date.

## Verification

- Every new scope: `coverage/<jur>/<class>/<version>.json` `complete: true`, `missing_from_provisions: []`,
  `extra_provisions: []`, `duplicate_provision_citations: []` (49 files checked by script); every document has at least
  one row with a non-empty body; the key figures (QMB/SLMB/QI, $1,330; $1,696/$1,305, October 1, 2025) were checked in
  the extracted bodies per document.
- Queue rows: 36 rows appended to the Medicare queue and 25 to the SNAP completion queue, one per jurisdiction, each
  verified against the coverage files on disk (`taken_count` = documents in the scope, 0 for pointers); the existing
  rows and the multiple federal rows of the SNAP completion queue are untouched (diff: 5 lines removed, the
  `status_counts` blocks).
- `uv run ruff check .`: clean.
- Focused tests: see the test line at the end of this section.
- `validate-release --ignore-r2-missing` on the draft selector: `ok: true`, 0 errors, 546 pre-existing warnings.

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or snap or medicare"`
in the sparse worktree (dev extra synced; without it `uv run pytest` falls through to the Anaconda Python 3.10 pytest on
PATH and every module fails collection): 306 passed, 3 skipped, 66 failed, all on other scopes' `data/corpus` artifacts
the sparse checkout does not contain (62 `FileNotFoundError` under `data/corpus/`, four assertions on the same missing
files: the state SNAP queue target check `us-al:target`, `is_file()` on retained sources, an empty retained-source
list). The `snap` keyword of the filter selects every state SNAP manual test, hence 66 rather than the ten of the
federal runs: `test_armenia_arlis`, `test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope`
(x2), `test_corpus_massachusetts` (x2), `test_israel_openlaw`, `test_recover_ingest` (uscode dry run),
`test_rulespec_be_source_promotion`, `test_state_snap_manual_queue` (x2), `test_uk_rulespec_release` (x2),
`test_us_rulespec_2026_08_08_obbb_alien_snap`, and the AK, AR, CA, CO, CT, DC, DE, IA, KY, LA, MD, ME, MI, MS, MT, ND,
NE, NJ, NM, NY, OK, PA, RI, SD, VA, WV SNAP scope tests. None mentions the new manifests, queue rows or generator
modules (grep of the log: 0 hits). No adapter was added, so no new tests.

## Controller

Selector additions (artifacts unsigned, on the controller's disk under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`,
not committed):

| jurisdiction | document_class | version |
| --- | --- | --- |
| us-az, us-co, us-dc, us-de, us-ga, us-hi, us-id, us-ks, us-ma, us-me, us-mn, us-ms, us-nj, us-nm, us-nv, us-ny, us-oh, us-or, us-ri, us-sc, us-sd, us-vt, us-wa | guidance | 2026-09-14-msp-income-standards |
| us-ct | policy | 2026-09-14-msp-income-standards |
| us-mi, us-nc, us-nh | manual | 2026-09-14-msp-income-standards |
| us-al, us-dc, us-de, us-hi, us-ia, us-id, us-ma, us-mn, us-mo, us-ms, us-ne, us-nj, us-nm, us-oh, us-or, us-ri, us-tn | guidance | 2026-09-14-snap-fy2026-state-transmittal |
| us-ks, us-nd, us-nh, us-ut, us-vt | manual | 2026-09-14-snap-fy2026-state-transmittal |

`docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.selector.json` is the 2026-09-13 federal-and-plans union plus these
49 scopes (810 scopes). No released scope is swapped or superseded; the pointer states add nothing. Remaining steps are
the controller's: `sign-ingest-manifest` for the 49 scopes, merge into the union selector, re-validate, sign, publish,
activate.

Rebuild:

```bash
uv run python scripts/build_msp_snap_state_charts_manifests.py            # manifests + queue rows (idempotent)
for m in manifests/us-??-msp-income-standards-2026.yaml; do
  s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-14-msp-income-standards --manifest "$m" --source-as-of 2026-09-14
  echo "elapsed_seconds=$(( $(date +%s) - s )) manifest=$m"
done
for m in manifests/us-??-snap-fy2026-state-transmittal.yaml; do
  s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-14-snap-fy2026-state-transmittal --manifest "$m" --source-as-of 2026-09-14
  echo "elapsed_seconds=$(( $(date +%s) - s )) manifest=$m"
done
uv run axiom-corpus-ingest validate-release --base data/corpus \
  --release docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.selector.json --ignore-r2-missing --max-issues 50
```
