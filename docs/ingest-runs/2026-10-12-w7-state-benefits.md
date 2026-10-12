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
  (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`), `--source-as-of 2026-10-12`; artifacts are unsigned and
  uncommitted. Nothing was signed, locked, pushed to R2 or loaded to Supabase; `manifests/releases/` and
  `manifests/program-bundles/` are untouched.
- Timing: started 15:19 EDT; held check and probes to 15:31; first extraction batch 15:33-15:35; Pennsylvania Code
  adapter 15:36; Minnesota (paced, see below) MN_TIMING; note and draft PR END_TIMING.
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

RESULTS_TABLE

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

MN_ACCESS

No CAPTCHA, mirror, repost, archived copy or proxy was used; TLS verification was never disabled; nothing was added to
`data/certs/`. Cornell LII (row 37) was not fetched: the row names the rule, and the official text was taken.

SCOPES_TABLE

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

OPEN_SECTION

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

CHECKS_SECTION

## Rebuild

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
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
