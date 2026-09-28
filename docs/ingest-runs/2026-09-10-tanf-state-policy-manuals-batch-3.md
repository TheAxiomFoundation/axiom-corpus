# TANF state policy manuals, batch 3

Date: 2026-09-10
Program: TANF (board Year 1 list; `manifests/tanf-agent-queue.yaml`)
Branch: `discovery/ingest-tanf` (worktree, sparse checkout without `data/corpus`; artifacts written to the shared corpus root of the main checkout, `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`, where `data/` is gitignored)

started_at: 2026-09-10T20:44:07Z (22:44:07+02:00; first command of this session, a previous attempt was killed at startup with a clean worktree)
finished_at: 2026-09-10T21:12:23Z (commit)
agent wall time: about 29 min (20:44 to 21:12Z; network waits: 5 min of 20 s probe timeouts, 7 min of WI HEAD requests)

## Batch rule (reviewer judgment 1)

Batches 1 and 2 covered every queue row and every alphabetical successor up to New Mexico, with states whose
TANF policy document is already in the corpus marked `done`. Batch 3 is the remainder of the 50 states plus DC
without a queue row. The queue's 46 state/DC jurisdictions were listed against the 51 and the missing five
were exactly **OH, RI, TN, VT, WI**. None of the five has a TANF cash-assistance policy manual or adopted rule in
the corpus (checked `manifests/` and `data/corpus/coverage/us-xx` in the main checkout, including today's scopes):
OH has OAC 5101:4 (SNAP), a statute recovery scope, HB 96 guidance and the LIHEAP/CCDF plans; RI has 218-RICR-20-00-1
(SNAP), tax statute/guidance and the LIHEAP plan; TN has the SNAP policy manual, 1240-01 chapters 02/03/04/08/12/14
(SNAP rules), the CHIP eligibility rule, tax documents and the LIHEAP plan; VT has the 3SquaresVT manual, tax
forms/statute and the LIHEAP plan; WI has the FoodShare handbook, the Medicaid eligibility handbook, tax documents
and the LIHEAP/CCDF plans. So no state was done by pointer; all five were probed once (plain request plus one
curl-cffi chrome impersonation attempt, 20 s timeouts).

Batch 3 = **OH, RI, TN, VT, WI**. Blocked publishers count as attempted.

## Results

| jurisdiction | status | document_class | documents taken / on index | provisions | elapsed s |
|---|---|---|---|---|---|
| us-oh | blocked_primary_source | manual | 0 / unknown | 0 | - |
| us-ri | extracted | regulation | 1 / 8 parts | 167 | 3 |
| us-tn | blocked_primary_source | manual | 0 / unknown | 0 | - |
| us-vt | blocked_primary_source | regulation | 0 / 12 rule PDFs (6 in the TANF family) | 0 | - |
| us-wi | extracted | manual | 291 / 291 | 846 | 41 |

Attempted 5, extracted 2 (RI, WI), blocked 3 (OH, TN, VT), done by pointer 0. Every one of the 51 jurisdictions
now has a queue row (52 rows with the federal row).

Provision total: 1,013 rows across 2 scopes (RI 1 document row + 166 page rows; WI 291 document rows + 555
block rows), every scope `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths. Uniqueness was
re-checked directly on each provisions JSONL, and every new `citation_path` was checked against every other
provisions JSONL under `data/corpus/provisions/us-ri/` (6 files) and `data/corpus/provisions/us-wi/` (7 files):
0 collisions. Version for both scopes: `2026-09-10-tanf-state-policy-manual`; document_class `manual` for the
WI agency manual and `regulation` for RI, whose primary policy document is the adopted rule the state publishes
itself (218-RICR-20-00-2).

Artifacts (unsigned, uncommitted, awaiting controller), per scope:

- `data/corpus/sources/<jur>/<class>/2026-09-10-tanf-state-policy-manual/official-documents/...`
- `data/corpus/inventory/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`
- `data/corpus/provisions/<jur>/<class>/2026-09-10-tanf-state-policy-manual.jsonl`
- `data/corpus/coverage/<jur>/<class>/2026-09-10-tanf-state-policy-manual.json`

## Index inventories

**Ohio (us-oh) - blocked.** Ohio Works First policy is published by ODJFS as the Cash Assistance Manual (CAM) on
its eManuals site, https://emanuals.jfs.ohio.gov/CashFoodAssist/CAM/, and codified as OAC 5101:1 on
https://codes.ohio.gov/ (Legislative Service Commission; the host of the ingested OAC 5101:4 SNAP scope
`us-oh-snap-rules`). Both hosts, probed once each at 20:46-20:47Z: plain `requests` ConnectTimeout after 20 s
(TCP connect never completed) and curl-cffi chrome impersonation "curl: (28) Connection timed out after 20002
milliseconds". No index could be inventoried, no workaround. `index_document_count` null. Retry from another
network (codes.ohio.gov answered plain clients in July).

**Rhode Island (us-ri, regulation).** Index: Department of State RICR Title 218 (DHS) Chapter 20 "Individual and
Family Support Programs", https://rules.sos.ri.gov/organizations/chapter/218-20. The chapter page is a DataTables
shell; each subchapter's parts table is loaded by the page's own XHR `/Organizations/get_parts/<subchapter id>`
(one subchapter, `218-20-00`). Family: 8 parts - 1 SNAP (218-RICR-20-00-1, already in the corpus as
`us-ri-snap-rules`), 2 Rhode Island Works Program Rules and Regulations, 3 General Public Assistance, 4 Child Care
Assistance Program, 5 SSI and State Supplemental Payment, 6 Refugee Assistance Program, 7 Social Services, 13 CCAP
for Child Care Educators and Staff. Taken: Part 2, following the part page's "Download Regulation" link to the
signed PDF of the active filing (`REG_13277_20250226153243922.pdf`, 166 pages, every page with native text, HTTP
Last-Modified 2025-02-26), page-level like the SNAP scope: `us-ri/regulation/218-ricr/20/00/2` and `.../page-N`.
The part page's Overview tab gives Type of Filing "Technical Revision", Regulation Status "Active", Effective
02/16/2025 (used as expression_date); its History tab lists 50 filings, the latest Amendment also effective
02/16/2025 (the technical revision only realigned §§ 2.15.6(K)(1) and (L)). rules.sos.ri.gov (Cloudflare) and
the S3 host answer plain clients, so the manifest carries no impersonation flag. Not taken: the other seven
parts (other programs).

**Tennessee (us-tn) - blocked.** TN DHS publishes the Families First policy manual as section PDFs on www.tn.gov
(DHS publications page https://www.tn.gov/humanservices/information-and-resources/dhs-publications.html, the
landing page of the ingested SNAP policy manual scope `us-tn-snap-policies`). Probed once at 20:47Z on the Families
First program page `/humanservices/for-families/families-first-tanf.html`: plain `requests` GET connected but
ReadTimeout after 20 s; curl-cffi chrome GET "curl: (28) Connection timed out after 20001 milliseconds". No index
could be inventoried, no workaround. `index_document_count` null. The Secretary of State's Families First rule
chapters (Tenn. Comp. R. & Regs. 1240-01-47 through 1240-01-50) are not in the corpus either (the existing us-tn
regulation scope holds 1240-01 chapters 02, 03, 04, 08, 12 and 14 only); noted on the row for the retry.

**Vermont (us-vt) - blocked, index inventoried.** DCF Economic Services Division publishes Reach Up policy as
adopted rules linked from its Current ESD Rules page, https://dcf.vermont.gov/esd/laws-rules/current (answers 200
to plain and chrome clients). Family: 12 rule PDFs - 2000 All Programs, 2100 Reach First, 2200 Reach Up, 2300
Reach Up Services, 2400 Post Secondary Education, 2500 Reach Ahead, 2600 General Assistance, 2700 AABD-EP, 2800
Emergency Assistance, 2900 Seasonal Fuel Assistance, 3000 Refugee Cash Assistance, 3100 Crisis Fuel - plus the
3SquaresVT manual link (already in the corpus), the Emergency Housing final proposed rules and the rules
renumbering bulletin. The TANF family would be 2000-2500 (6 files; 2000 carries the all-programs general rules).
Every rule file is hosted on outside.vermont.gov (SharePoint behind an F5 gateway): plain `requests` GET and
curl-cffi chrome HEAD/GET of `2200-Reach-Up.pdf` and `2000-All-Programs.pdf` all returned HTTP 403 text/html
309-311 bytes "The requested URL was rejected. Please consult with your administrator. Your support ID is ..."
(server `volt-adc`, "F5 site: fr4-fra") at 20:50-20:51Z. No document retrievable, no workaround. Retry from a US
network. document_class `regulation` (adopted rules the agency publishes itself).

**Wisconsin (us-wi, manual).** Index: DCF Wisconsin Works (W-2) Manual,
https://dcf.wisconsin.gov/manuals/w-2-manual/Production/default.htm, linked as "W-2 Manual" from the DCF W-2
policies page https://dcf.wisconsin.gov/w2/partners/policy (which also lists the EA Manual, the TJ/TMJ Manual
and 2 Wisconsin Administrative Code DCF chapter links on the legislature host - separate programs/families, not
taken). The manual is Adobe RoboHelp 2022 responsive output: `default.htm` is a redirect shell, the TOC is
`whxdata/toc.new.js` (top-level books) plus one `whxdata/toc<N>.new.js` per book. Family: 119 book files, 291
items resolving to 291 topic pages (Welcome, chapters 01 W-2 Introduction through 18 Emergency Assistance and
related programs, appendices). Taken: all 291, `us-wi/manual/dcf/w2/<slug of the topic path>` (e.g.
`.../01-01-1-1-w-2-overview`, `.../appendices-appendix-tanf-work-participation-requirements`), topic titles from
the TOC names; expression_date = each page's HTTP Last-Modified (2026-07-03 for all 291, the site's last
republish). Extraction `html_content_selector: #rh-topic` with `html_drop_selectors`
`#rh-topic > div:first-child > table:has(p.layout)` (the master page's banner table "Division of Family and
Economic Security ... Wisconsin Works (W-2) Manual", which the first run emitted as an identical block-1 in all
291 topics) and `span[data-close-text]` (RoboHelp expand-spots repeat the trigger text, e.g. "W-2 W-2 Wisconsin
Works", in 201 blocks of the first run; the open text and the expansion text are kept). First run: 1,137 rows
(291 banner blocks, 201 duplicated triggers); rerun: 846 rows, 0 of either. dcf.wisconsin.gov answers plain
clients, so no impersonation flag.

## Retries of earlier blocked rows

None: the work order for batch 3 did not include retries of NY, OR, SC, KY or NE, and all are network/geo blocks
best retried from a US network.

## Code changes

- `scripts/build_tanf_state_policy_manual_manifests.py` (existing generator, extended rather than a new script):
  `BATCH_3`, `BATCH_LABEL` extended (queue notes say "Batch 3."), five new `NEW_ROWS` entries (OH, RI, TN, VT, WI;
  the placeholder note now names the row's batch), `BLOCKED` entries for OH, TN, VT, builders `build_ri` and
  `build_wi`, `BUILDERS` wiring, docstring header. `--only us-ri --only us-wi` rebuilt only the two new manifests;
  no earlier state's manifest was regenerated (git shows only the two new manifest files, the script and the queue).
- No changes under `src/` or `tests/`: no publisher needed a new adapter. RI uses the default PDF page-level path
  (the same as `us-ri-snap-rules`); WI uses the existing HTML content/drop selectors. The batch-1 DOCX mode was not
  needed. No TLS chain repair was needed (no `data/certs` additions this batch).
- GitNexus MCP tools were unavailable in this session, so no impact analysis was run; no existing function outside
  the generator script was modified.
- `uv run ruff check scripts/build_tanf_state_policy_manual_manifests.py`: all checks passed.

## Reviewer judgments

1. Batch rule: the five jurisdictions without a queue row (OH, RI, TN, VT, WI) confirmed against the 51; none had
   a TANF policy document in the corpus, so none was done by pointer.
2. Blocked publishers OH (TCP connect timeouts on both the ODJFS eManuals host and codes.ohio.gov), TN (www.tn.gov
   read/connect timeouts) and VT (F5 403 on outside.vermont.gov for every rule file) count as attempted. OH and TN
   look like network-path problems from this environment rather than deliberate blocks (codes.ohio.gov and
   www.tn.gov both served earlier scopes); VT is an explicit gateway rejection. All three: retry from a US network
   before assigning adapter work.
3. `regulation` for RI (218-RICR-20-00-2, Department of State publication of the DHS rule) with the existing RI
   citation convention `us-ri/regulation/218-ricr/20/00/2`, and for the VT row (DCF-published adopted rules);
   `manual` for WI (`us-wi/manual/dcf/w2/...`) and for the OH and TN rows (agency manuals).
4. RI: only Part 2 taken from the 8-part chapter; the SNAP part is already in the corpus and the other six parts
   are other programs. expression_date = the active filing's effective date (2025-02-16), which is also the latest
   substantive Amendment's effective date (the active filing is a same-day Technical Revision).
5. RI extraction page-level (as the SNAP rule scope); WI topic-page HTML blocks (as PA/NH), with the banner table
   and the expand-spot duplicate spans dropped (second run) - the glossary expansion text itself is kept inline.
6. WI: the whole W-2 Manual taken, including chapter 18 (Emergency Assistance and related programs) and the
   appendices, because they are chapters of the W-2 Manual's own TOC; the separate EA and TJ/TMJ manuals not taken.
7. VT index inventory recorded on the blocked row (12 rule PDFs, TANF family 2000-2500) so the retry can start
   from a known document list; `index_document_count` 12, `taken_count` 0.
8. expression_date choices: RI the filing's effective date; WI HTTP Last-Modified per page.
9. Tests: the focused subset passes except the 10 known sparse-worktree failures (below).

## Timing

Per-jurisdiction extraction seconds (full runs, shared corpus root): RI 3 (2.7), WI 41 (first run 41.0, rerun
41.5 after the drop-selector change). Probes: 20:46:10-20:51:08Z (OH two hosts 4 x 20 s, TN 2 x 20 s, RI/VT/WI
sub-second to 3 s, VT file host 403 in 0.1 s). Manifest generation: RI + WI in one run 20:57:18-21:00:51Z (3 min
33 s, WI 291 HEADs); WI regeneration 21:05:11-21:08:35Z (3 min 24 s). Extraction: RI 21:01:25Z, WI 21:01:30Z and
21:08:57Z. Tests 40 s each of two runs.

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 256 passed, 10 failed, 2 skipped in the worktree (40 s; run twice, after each script change). The 10 failures
are the expected `FileNotFoundError`s on `data/corpus/...` artifacts absent from this sparse checkout:
test_be_rulespec_2026_08_23_promotion, test_build_ny_tanf_compatibility_scope (2), test_rulespec_be_source_promotion,
test_us_ak_snap_manual, test_us_ct_snap_manual, test_us_mi_snap_manual, test_us_mt_snap_manual,
test_us_nd_snap_manual, test_us_ny_snap_manuals. No other failure.

## Rebuild

```bash
uv run python scripts/build_tanf_state_policy_manual_manifests.py --only us-ri --only us-wi   # fetches both indexes live (WI: 291 HEADs, about 3.5 min)
for st in ri wi; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base data/corpus --version 2026-09-10-tanf-state-policy-manual \
    --manifest manifests/us-$st-tanf-state-policy-manual.yaml
done
```

No credentials read or written. No `REQUESTS_CA_BUNDLE` was needed for any host this batch.

## Remaining

Blocked or pending publishers: OH, TN, VT (this batch), SC, KY, NE (batch 2), NY (bot challenge), OR (DNS) - all
to retry from a US network; NM (reviewer decision on the RealFile index). Federal: 45 CFR 260-265 via
`extract-ecfr`, and the ACF OFA state plan index (unchanged). Known batch-1 issue left alone per the work order:
the us-co scope's sections 3.606.1, 3.606.2, 3.606.6 share citation paths with `us-co/regulation/2026-07-13-recovery`.
Controller: `sign-ingest-manifest` per scope (16 agent_ready scopes now), immutable release selector,
`publish_corpus.py --dry-run`, publish.

## Closing table: all 51 jurisdictions and their final queue status

Tally (50 states + DC): done 26, agent_ready 16, blocked_primary_source 8, needs_review 1. The federal row
(`us`) is `needs_review`, so the queue's `status_counts` are needs_review 2, done 26, agent_ready 16,
blocked_primary_source 8 (52 rows).

| jurisdiction | name | queue_status | document_class | target_manifest |
|---|---|---|---|---|
| us-ak | Alaska | done | regulation | manifests/us-ak-atap-regulations.yaml |
| us-al | Alabama | done | policy | manifests/us-al-tanf-official-documents.yaml |
| us-ar | Arkansas | done | policy | manifests/us-ar-tea-official-documents.yaml |
| us-az | Arizona | done | manual | manifests/us-az-des-faa5-manual.yaml |
| us-ca | California | agent_ready | regulation | manifests/us-ca-tanf-state-policy-manual.yaml |
| us-co | Colorado | agent_ready | regulation | manifests/us-co-tanf-state-policy-manual.yaml |
| us-ct | Connecticut | done | policy | manifests/us-ct-ssp-official-documents.yaml |
| us-dc | District of Columbia | agent_ready | manual | manifests/us-dc-tanf-state-policy-manual.yaml |
| us-de | Delaware | done | regulation | manifests/us-de-tanf-rules.yaml |
| us-fl | Florida | done | manual | manifests/us-fl-ess-manual.yaml |
| us-ga | Georgia | done | manual | manifests/us-ga-tanf-manual.yaml |
| us-hi | Hawaii | done | regulation | manifests/us-hi-tanf-admin-rules.yaml |
| us-ia | Iowa | done | regulation | manifests/us-ia-fip-admin-rules.yaml |
| us-id | Idaho | agent_ready | regulation | manifests/us-id-tanf-state-policy-manual.yaml |
| us-il | Illinois | done | manual | manifests/us-il-snap-manual.yaml |
| us-in | Indiana | done | manual | manifests/us-in-snap-manual.yaml |
| us-ks | Kansas | done | manual | manifests/us-ks-keesm.yaml |
| us-ky | Kentucky | blocked_primary_source | manual | manifests/us-ky-tanf-state-policy-manual.yaml |
| us-la | Louisiana | agent_ready | manual | manifests/us-la-tanf-state-policy-manual.yaml |
| us-ma | Massachusetts | done | regulation | manifests/us-ma-tafdc-regulations.yaml |
| us-md | Maryland | done | regulation | manifests/us-md-tca-guidance-official-documents.yaml |
| us-me | Maine | done | regulation | manifests/us-me-tanf-regulation-official-documents.yaml |
| us-mi | Michigan | done | manual | manifests/us-mi-bridges-manual.yaml |
| us-mn | Minnesota | done | manual | manifests/us-mn-combined-manual.yaml |
| us-mo | Missouri | agent_ready | manual | manifests/us-mo-tanf-state-policy-manual.yaml |
| us-ms | Mississippi | agent_ready | manual | manifests/us-ms-tanf-state-policy-manual.yaml |
| us-mt | Montana | agent_ready | manual | manifests/us-mt-tanf-state-policy-manual.yaml |
| us-nc | North Carolina | done | manual | manifests/us-nc-work-first-manual-official-documents.yaml |
| us-nd | North Dakota | agent_ready | manual | manifests/us-nd-tanf-state-policy-manual.yaml |
| us-ne | Nebraska | blocked_primary_source | regulation | manifests/us-ne-tanf-state-policy-manual.yaml |
| us-nh | New Hampshire | agent_ready | manual | manifests/us-nh-tanf-state-policy-manual.yaml |
| us-nj | New Jersey | done | regulation | manifests/us-nj-wfnj-rules.yaml |
| us-nm | New Mexico | needs_review | regulation | manifests/us-nm-tanf-state-policy-manual.yaml |
| us-nv | Nevada | done | manual | manifests/us-nv-eligibility-payments-manual.yaml |
| us-ny | New York | blocked_primary_source | manual | manifests/us-ny-tanf-state-policy-manual.yaml |
| us-oh | Ohio | blocked_primary_source | manual | manifests/us-oh-tanf-state-policy-manual.yaml |
| us-ok | Oklahoma | agent_ready | regulation | manifests/us-ok-tanf-state-policy-manual.yaml |
| us-or | Oregon | blocked_primary_source | regulation | manifests/us-or-tanf-state-policy-manual.yaml |
| us-pa | Pennsylvania | agent_ready | manual | manifests/us-pa-tanf-state-policy-manual.yaml |
| us-ri | Rhode Island | agent_ready | regulation | manifests/us-ri-tanf-state-policy-manual.yaml |
| us-sc | South Carolina | blocked_primary_source | manual | manifests/us-sc-tanf-state-policy-manual.yaml |
| us-sd | South Dakota | agent_ready | regulation | manifests/us-sd-tanf-state-policy-manual.yaml |
| us-tn | Tennessee | blocked_primary_source | manual | manifests/us-tn-tanf-state-policy-manual.yaml |
| us-tx | Texas | done | manual | manifests/us-tx-manuals.yaml |
| us-ut | Utah | done | regulation | manifests/us-ut-fep-official-documents.yaml |
| us-va | Virginia | agent_ready | manual | manifests/us-va-tanf-state-policy-manual.yaml |
| us-vt | Vermont | blocked_primary_source | regulation | manifests/us-vt-tanf-state-policy-manual.yaml |
| us-wa | Washington | done | manual | manifests/us-wa-eaz-manual.yaml |
| us-wi | Wisconsin | agent_ready | manual | manifests/us-wi-tanf-state-policy-manual.yaml |
| us-wv | West Virginia | done | manual | manifests/us-wv-manuals.yaml |
| us-wy | Wyoming | done | manual | manifests/us-wy-manuals.yaml |

The `target_manifest` of a blocked row is the manifest path the builder will write once the publisher is
reachable; those five files do not exist yet.
