# Wave 7, group `state-benefits`: state SNAP, TANF, CCDF, Medicaid/CHIP, SSI and UI documents

Date: 2026-10-12 (America/New_York).
Work order: `docs/coverage/program-bundle-gaps-2026-10-12/wave7/00-common-preamble.md`, `wave7/state-benefits-brief.md`
and `wave7/state-benefits.csv` (79 rows, 75 Tier 1, 23 jurisdictions).
Decisions: `docs/ingest-runs/2026-10-12-w7-state-benefits-decisions.csv`, exactly one row per work-order row (79); the
`id` is the work-order `id`.
Generator: `scripts/build_w7_state_benefits_manifests.py` (every official-documents manifest of this run and the
decisions file). Minnesota extraction: `scripts/extract_w7_state_benefits_mn.py`.

## Worktree, branch, timing, disk

- Sparse worktree `~/axiom-corpus-worktrees/w7-state-benefits`, branch `discovery/ingest-w7-state-benefits` cut from
  `main` 89dc519fa. `data/corpus/` excluded, never symlinked. Every extraction wrote to the main checkout's corpus root
  (`--base <axiom-corpus checkout>/data/corpus`), `--source-as-of 2026-10-12`; artifacts are unsigned and
  uncommitted. Nothing was signed, locked, pushed to R2 or loaded to Supabase; `manifests/releases/` and
  `manifests/program-bundles/` are untouched.
- Timing: started 15:19 EDT; held check and probes to 15:31; first extraction batch 15:33-15:35; Pennsylvania Code
  adapter 15:36; Minnesota: four pages answered the probe at 15:24, every later request (15:24-16:11, after pauses of 7 and 34
  minutes) got the Radware page; the four retained pages were replayed at 16:13; note and draft PR about 16:20. About
  1 hour of the 3-hour box.
- Disk: `df -h /` 3.2 TiB free before every batch and at the end (the 50 GB stop line was never near).
- Impact analysis: not run (the GitNexus MCP tools are not available in this session). No library function under
  `src/` was changed.

## Method

1. Held already? Every row's `bundle_url`, `check_final_url` and `id` were normalised (host without `www.`, decoded
   path, query kept minus a trailing `&` or `&d=reduce`) and matched against every URL-valued field of every local
   inventory of the 23 jurisdictions and `us`, plus the inventories of locked scopes read from the corpus cache
   (`~/.axiom/corpus-cache`, 33,212 addresses; two locked inventories have no bytes locally:
   `us-co/regulation/2026-07-13-recovery-r2026-09-11-tanf-consolidated-r2026-09-27-ccap-sections` and an SC statute
   scope, both read through their lock file lists). Query-routed addresses were also matched by their key
   (`item=`, `dDocName=`, `dID=`, `ruleVersionId=`) against every citation path and URL, and the citation paths and
   headings of the jurisdiction's provisions were searched for the section numbers. PDFs that looked like a held
   document were compared by SHA-256 with the held source file. Every held path was checked against the served
   selector `us-rulespec-2026-10-07-w6-bundle-gaps-union`.
2. One plain probe of every remaining address with the corpus user agent (the extractor's browser user agent only on
   403/404/406), TLS verified with certifi plus `data/certs/`, one request at a time per host, 1.5 s apart; the
   Minnesota DHS host with the documented curl_cffi `chrome120` profile. Every body was read for title, edition and
   date before an entry was written.
3. Manifests: one per (jurisdiction, class), `manifests/<jur>-state-benefits-w7-<class>.yaml`, version
   `2026-10-12-w7-state-benefits-<class>-<st>`. `source_url` is the bundle address exactly wherever that address was
   the one fetched (query included); otherwise the bundle address is in `metadata.bundle_url` and the decision row's
   `official_url` names the address fetched. `expression_date` is the date the document prints (effective, approval,
   filing or memo date, recorded in `expression_date_note`), else the fetch date.
4. Every scope: coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths; no document under 300
   characters of body text; no challenge page stored; `scripts/validate_citation_paths.py` over the new provisions:
   `RESULT: OK`. No new path collides with any provisions file of its jurisdiction on disk.

## Results by status

| action | PRESENT | ALREADY-HELD | OUTREACH | ABSENT | OUT-OF-SCOPE | SKIPPED | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MEASURE-CHECK | 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| FETCH | 37 | 12 | 12 | 0 | 0 | 0 | 61 |
| CHECK-PUBLISHER | 1 | 7 | 0 | 0 | 0 | 0 | 8 |
| OFFICIAL-SOURCE | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| DEAD-LINK | 3 | 2 | 0 | 0 | 0 | 0 | 5 |
| total | 42 | 25 | 12 | 0 | 0 | 0 | 79 |

By program (a row counts once per program it names): CCDF 21 (16 PRESENT, 5 ALREADY-HELD); TANF 31 (14 PRESENT,
5 ALREADY-HELD, 12 OUTREACH); SNAP 15 (7 PRESENT, 8 ALREADY-HELD); SSI 8 (3 PRESENT, 5 ALREADY-HELD); Medicaid and
CHIP 3 each (1 PRESENT, 2 ALREADY-HELD); UI 1 (PRESENT). The work order has no WIC or LIHEAP row.

DEAD-LINK rows: the four Pennsylvania Code addresses timed out once in the triage but answered the adapter (two
PRESENT, two inside the held chapter 183 PDF); the Maryland 11.9.2024 plan file is 404 and joins to the Amendment 1
plan that superseded it.

## Publisher access (2026-10-12)

Answered the plain corpus client (HTTP 200, documents taken or compared): humanservices.arkansas.gov,
spl.cde.state.co.us (Colorado State Publications Library), www.coloradosos.gov and www.sos.state.co.us
(`GenerateRulePdf.do`), www.dcregs.dc.gov / dcregs.dc.gov (chapter page and its `DownloadFile` .doc),
www.leg.state.fl.us, flrules.org, humanservices.hawaii.gov, idec.illinois.gov, www.dhs.state.il.us (16 `page.aspx`
items; item 104995 redirects to idec.illinois.gov), apps.legislature.ky.gov, earlychildhood.marylandpublicschools.org
(the Amendment 1 filedepot PDF; the 2024 file 404s; the Cloudflare block of September did not recur on these paths),
www.legislature.mi.gov, dese.mo.gov (the Drupal antibot form of September did not recur on the 2026/04 PDF),
dssmanuals.mo.gov, policies.ncdhhs.gov, pub.njleg.gov, www.nj.gov, www.dss.nv.gov,
risos-apa-production-public.s3.amazonaws.com (RI Secretary of State rules store), scchildcare.org,
lawfilesext.leg.wa.gov, dfs.wyo.gov, www.pacodeandbulletin.gov (through the Pennsylvania Code adapter; the
triage's one-GET timeout did not recur).

Documented fallbacks used: `drxya2s1hkmtl.cloudfront.net` (Indiana General Assembly IAR API, `browser_impersonation`,
docs/ingest-runs/2026-09-14-state-tax-regulations.md) for 455 IAC; `www.dhs.state.mn.us` (Radware; `chrome120`,
docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md and 2026-09-14-liheap-matrix-ssi-standards.md).

Blocked (OUTREACH, not worked around): `www.dhs.state.mn.us`. The documented `chrome120` profile answered the first
four pages of the probe (15:24 EDT; ESM 3.9, CM 0011.21, 0017.12.03, 0018.09) and from then on returned the Radware
challenge page (HTTP 200, `<title>Radware Page</title>`, 118,391 bytes) to every request: the rest of the probe
(1.5 s apart), a paced extraction run after a 7-minute pause (first request challenged) and one request after a
further 34 minutes. Twelve rows stay OUTREACH: CM 0018.18 and 0020.09 and the ten `dID=` addresses (stored
revisions; not identified, since each request returned the challenge). The four pages that answered are extracted
from the bytes the probe took from the official address with the documented profile, replayed through the
supported `local_path` field on an untracked manifest copy (`scripts/extract_w7_state_benefits_mn.py --retained`,
the de-kindergeld precedent); their inventory `download_url` therefore names the local replay file. SHA-256 of the
retained pages: ESM 3.9 `3b873dc9...`, CM 0011.21 `fd19f074...`, 0017.12.03 `4d6ab1bf...`, 0018.09 `7a89283f...`.
The served Combined Manual PDF (`us-mn/manual/dhs/combined-manual/current`, fetched 2026-05-27) carries older texts of
these sections (issue dates 2014-2020, e.g. 0020.09 at page 900 with the 10/2020 MFIP standards), so it is not
recorded as holding them.

No CAPTCHA, mirror, repost, archived copy or proxy was used; TLS verification was never disabled; nothing was added to
`data/certs/`. Cornell LII (row 37) was not fetched: the row names the rule, and the official text was taken.

## Scopes

21 new scopes, 741 provision rows, 3,139,902 characters, 13.3 MB of source snapshots. Every scope reports coverage
`complete: true`, 0 missing, 0 extra, 0 duplicate citation paths. Seconds are the wall time of one extraction call,
download included.

| jurisdiction | class | version | documents | rows | chars | source MB | s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| us-co | regulation | `2026-10-12-w7-state-benefits-regulation-co` | 1 | 140 | 259,528 | 0.72 | 3 |
| us-dc | regulation | `2026-10-12-w7-state-benefits-regulation-dc` | 1 | 2 | 1,886 | 0.05 | 2 |
| us-fl | statute | `2026-10-12-w7-state-benefits-statute-fl` | 1 | 2 | 22,794 | 0.06 | 3 |
| us-il | guidance | `2026-10-12-w7-state-benefits-guidance-il` | 3 | 26 | 16,805 | 0.24 | 2 |
| us-il | manual | `2026-10-12-w7-state-benefits-manual-il` | 13 | 98 | 74,156 | 0.22 | 3 |
| us-il | policy | `2026-10-12-w7-state-benefits-policy-il` | 1 | 42 | 819,384 | 3.09 | 4 |
| us-in | regulation | `2026-10-12-w7-state-benefits-regulation-in` | 1 | 116 | 164,655 | 0.52 | 2 |
| us-ky | statute | `2026-10-12-w7-state-benefits-statute-ky` | 2 | 4 | 10,079 | 0.03 | 1 |
| us-md | policy | `2026-10-12-w7-state-benefits-policy-md` | 1 | 42 | 728,021 | 3.05 | 5 |
| us-mi | statute | `2026-10-12-w7-state-benefits-statute-mi` | 1 | 2 | 3,113 | 0.02 | 3 |
| us-mn | manual | `2026-10-12-w7-state-benefits-manual-mn` | 4 | 10 | 20,347 | 0.64 | 1 (replay) |
| us-mo | manual | `2026-10-12-w7-state-benefits-manual-mo` | 2 | 11 | 23,663 | 0.04 | 1 |
| us-mo | policy | `2026-10-12-w7-state-benefits-policy-mo` | 1 | 42 | 540,031 | 2.69 | 4 |
| us-nc | guidance | `2026-10-12-w7-state-benefits-guidance-nc` | 1 | 3 | 2,072 | 0.07 | 2 |
| us-nj | rulemaking | `2026-10-12-w7-state-benefits-rulemaking-nj` | 1 | 21 | 30,967 | 0.07 | 1 |
| us-nj | statute | `2026-10-12-w7-state-benefits-statute-nj` | 1 | 2 | 31,143 | 0.04 | 2 |
| us-pa | regulation | `2026-10-12-w7-state-benefits-regulation-pa-title-34-chapter-65` | adapter | 81 | 126,584 | 0.54 | 2 |
| us-pa | regulation | `2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-177` | adapter | 17 | 52,174 | 0.45 | 2 |
| us-pa | regulation | `2026-10-12-w7-state-benefits-regulation-pa-title-55-chapter-178` | adapter | 67 | 190,520 | 0.62 | 3 |
| us-wa | rulemaking | `2026-10-12-w7-state-benefits-rulemaking-wa` | 2 | 4 | 7,654 | 0.01 | 2 |
| us-wy | guidance | `2026-10-12-w7-state-benefits-guidance-wy` | 1 | 9 | 14,326 | 0.12 | 3 |

The Illinois guidance and Kentucky statute scopes were re-extracted once under the same, unreleased version (a drop
selector for the IDEC page footer and calculator; the printed effective date of KRS 205.200).

## Families and decisions

- **CCDF plans.** Amendments and editions not held: Illinois Amendment 2 (approved 2026-07-01, sibling path
  `us-il/policy/acf/ccdf-plan/fy2025-2027-amendment-2`; the served IL plan is the initial plan from DHS item 163746),
  Maryland Amendment 1 (approved 2025-06-24) and Missouri Amendment 2 (approved 2026-03-26), the first Maryland and
  Missouri plan text in the corpus (both were blocked in the 2026-09-10 plan run), at
  `us-md|us-mo/policy/acf/ccdf-plan/fy2025-2027`. Same ACF-118 labeled-section extraction as the 2026-09-10 scopes
  (42 rows each). The Maryland 11.9.2024 approval file (row 42) answers 404 and the MSDE plan page links no 2025-2027
  file, so row 42 joins to the Amendment 1 path. Held: the Colorado State Publications Library copy and the Nevada
  `__3` file are byte-identical to the held plans; Louisiana and Wyoming differ only by a query string; the South
  Carolina "submitted version as of 7-1-24" is superseded by the held approved plan.
- **Illinois DHS pages.** CCAP Policy Manual sections (01.01.03, 01.02.01 in its 2022-07-01 and 2026-07-01 editions,
  01.02.02, 01.02.03, 04.02.01, 06.03.01, 06.05.01 and its 7/1/2025 rates page) at `us-il/manual/dhs/ccap/<item>`
  (item numbers keep the two editions of one section apart, the CSMM convention); manual releases MR 18.17, 23.30,
  24.12 and WAG 03-03-01 at `us-il/manual/dhs/csmm/<item>` beside the held CSMM items (MR 23.22 is held there too);
  the TANF service page, brochure 586 and the CCAP page (redirect to IDEC) as guidance. Content selector `#Main2`.
- **Colorado rules.** Five `GenerateRulePdf.do?ruleVersionId=` addresses without a file name name superseded versions
  of 9 CCR 2503-5 (two), 9 CCR 2503-6, 10 CCR 2505-10 8.100 and 10 CCR 2506-1; the current versions are served at the
  paths the wave-7 rejoin builder used for other versions of the same rules: ALREADY-HELD. 8 CCR 1403-1
  ruleVersionId 12658 (eff. 08/14/2026) is newer than the served 11042 (eff. 08/14/2023; see
  docs/ingest-runs/2026-09-27-co-8-ccr-1403-1-sections.md), so it is taken page-level at the dated sibling path
  `us-co/regulation/8-ccr-1403-1-eff-2026-08-14`.
- **Superseded editions with the current text served** (ALREADY-HELD, the wave-6 precedent): the 2020 Arkansas
  Complete SNAP Manual compilation, the 2014 posting of HAR 17-676, the October 2014 Rhode Island SNAP rules
  (superseded by 218-RICR-20-00-1), and the Colorado rule versions above.
- **Minnesota.** ESM 3.9 and Combined Manual 0011.21, 0017.12.03 and 0018.09 (issue date 03/2026) at
  `us-mn/manual/dhs/mfip-employment-services-manual/3.9` and `us-mn/manual/dhs/combined-manual/<section>`, beside the
  served whole-manual PDF; the rest of the Minnesota rows are OUTREACH (above).
- **Minnesota.** ESM 3.9 and Combined Manual 0011.21, 0017.12.03 and 0018.09 (issue date 03/2026) at
  `us-mn/manual/dhs/mfip-employment-services-manual/3.9` and `us-mn/manual/dhs/combined-manual/<section>`, beside the
  served whole-manual PDF; the other twelve Minnesota rows are OUTREACH (publisher access, above).
- **Statutes and session laws.** Fla. Stat. 414.095 (2025), KRS 205.200 (the bundle's id=54926 is an LRC "Invalid
  Statute" notice; the current version, id=57029, effective 2026-04-14, is taken) and 205.245, MCL 400.10, P.L. 2013
  c.45 (NJ), DCMR 29-7200 (the chapter page's one section, the `.doc` behind `DownloadFile`, effective 2026-05-22).
- **Regulations.** 455 IAC Article 1 (2026 IAC, 115 sections incl. 1-3-3, from the Indiana Register API) for the
  Cornell row; 55 Pa. Code chapters 177 and 178 and 34 Pa. Code chapter 65 through the Pennsylvania Code adapter; 55
  Pa. Code chapter 183 (rows 68, 71, 72) is served as the wave-6 chapter PDF.
- **Rulemaking and memos.** WSR 09-15-085 and 09-16-095, NJ PRN 2016-017 (48 N.J.R., May 2, 2016), MO IM-39 (2003)
  and IM-34 (2013), NC Economic Services Administrative Letter 6-2005, the Wyoming DFS child care page.

## MEASURE-CHECK rows

- AZ Title 46 (row 1): served as `us-az/statute/title-46` (scope `2026-10-06-w6-benefits-snap-statute-us-az-title-46`,
  in the served selector); the bundle names `us-az/statute/46`: a `path_moves` entry `us-az/statute/46 ->
  us-az/statute/title-46`.
- CO FNS food-restriction waiver documents (rows 3-5): held and served (`us-co/policy/2026-07-21-co-snap-policy`, same
  source URLs, locked bytes match). They count missing because the bundle's full-tier entry comes from
  `manifests/us-co-snap-primary-policy.yaml`, whose entries carry no `citation_path` (the extractor derives the path
  from `source_id`), and `scripts/build_program_bundle.py` applies `joins.yaml` `document_paths` only to PolicyEngine
  and plan rows. The joins already exist; the builder (or the manifest) needs to carry them to manifest-sourced
  entries. Recorded ALREADY-HELD with the served paths.

## OUTREACH (12), ABSENT (0), OUT-OF-SCOPE (0), SKIPPED (0)

- OUTREACH: twelve Minnesota DHS addresses (CM 0018.18 and 0020.09; `dID=128565`, `128623`-`128629`, `139469`,
  `160643`): Radware challenge to the documented profile throughout the run. A static or bulk export of the eManuals
  (or an allowlisted fetch) from Minnesota DHS would close them; the served CM PDF holds older texts of 0018.18 and
  0020.09.
- Nothing was ABSENT, OUT-OF-SCOPE or SKIPPED.

## Controller

- Selector additions: the scopes of the table (all unsigned, on the controller's disk).
- Shared containers: the three Pennsylvania Code scopes each emit `us-pa/regulation` and their title container
  (`title-55` twice, `title-34`); `us-pa/regulation` is also in the income-tax title-61 scope. Fold as the earlier
  adapter consolidations did.
- 8 CCR 1403-1: the new dated sibling holds the current edition page-level; the served 11042 scope and the locked
  `-r2026-09-27-ccap-sections` re-version (queued for Max) hold the 2023 edition. A later sections build of 12658
  could replace both.
- Joins: where `official_url` differs from `bundle_url` (KRS 205.200, 455 IAC, the MD 2024 plan, the PA chapters and
  section, the held rows with a query-string difference) the decision row carries the address actually fetched or held.

## Checks

- Coverage of all 21 scopes: `complete: true`, no duplicate path, no missing or extra inventory entry; every manifest
  entry's `source_url`, `expression_date` and title match the extracted inventory and provisions.
- `uv run --extra dev python scripts/validate_citation_paths.py --provisions <tree of the 21 new files>`: 741 records,
  738 unique paths (the three Pennsylvania Code containers repeat across the adapter scopes), `RESULT: OK`; new
  irregular segments 137 `block-N`, 161 `page-N`, 1 collection root (`us-pa/regulation`).
- Collisions: the new paths were intersected with every other provisions file of the same jurisdiction on disk; the
  only shared path is the `us-pa/regulation` root (also in the income-tax title-61 scope).
- `uv run --extra dev ruff check` on the two scripts: clean (`ruff format` applied).
- `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or
  official_documents"`: 297 passed, 2 skipped, 18 failed; every failure is a `FileNotFoundError` on another scope's
  `data/corpus` artifact the sparse worktree does not hold (Armenia ARLIS, BE promotion x2, NY TANF compatibility x2,
  Wisconsin pit-west replay, Israel OpenLaw, SC act 110 successor, AK/CT/MI/MT/ND/NY SNAP manuals, SNAP child-support
  CA/DE x4), the known set of the wave-6 notes.
- `changelog.d/wave7-state-benefits.added.md` added.

## Rebuild

```bash
B=<axiom-corpus checkout>/data/corpus
export REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>
uv run --extra dev python scripts/build_w7_state_benefits_manifests.py
for m in manifests/*-state-benefits-w7-*.yaml; do
  case $m in *us-mn-*) continue;; esac
  v=$(grep -m1 '^version:' "$m" | awk '{print $2}')
  uv run --extra dev axiom-corpus-ingest extract-official-documents --base $B --version "$v" --manifest "$m" --source-as-of 2026-10-12
done
uv run --extra dev python scripts/extract_w7_state_benefits_mn.py --base $B --pause 60
for tc in 55:178 55:177 34:65; do
  uv run --extra dev axiom-corpus-ingest extract-pennsylvania-code --base $B --version 2026-10-12-w7-state-benefits-regulation-pa \
    --only-title ${tc%%:*} --only-chapter ${tc##*:} --source-as-of 2026-10-12 --workers 1
done
```
