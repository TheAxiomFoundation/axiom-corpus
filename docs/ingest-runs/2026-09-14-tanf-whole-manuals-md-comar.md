# TANF whole manuals (CT, GA, DE; AZ blocked) and the Maryland COMAR chapter-03 consolidation

Date: 2026-09-14 (UTC; the evening of 2026-09-13 on the controller's machine)
Work order: the "slice taken, publisher posts whole" row of the needs-driven closure check
(`docs/coverage/needs-closure-2026-09-11/tanf.md`: CT 28, GA 20, AZ 13, DE 17 EXTRACTABLE cells, 78 in all) and the
held-out Maryland COMAR chapter-03 scope of `docs/ingest-runs/2026-09-11-release-consolidation.md`.
Branch `discovery/ingest-tanf-whole-manuals-md-comar` cut from `origin/main` (421ffbea4, later moved to 5c2505ec6, the
CMS state-plans merge) in the sparse worktree `~/axiom-corpus-worktrees/tanf-whole` (`data/corpus/` excluded, never
symlinked); every extraction and the consolidation wrote to the main checkout's corpus root
(`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`). Agent timing: worktree created 2026-09-14T01:09Z; probes,
GA, DE and the MD consolidation done by 01:35Z; the session was then suspended (an API rate limit) and resumed at
14:05Z, when `origin/main` had moved: the branch, which had no commits of its own, was moved to the new head with the
uncommitted work stashed around the reset (no conflicts) and `uv sync` re-run; the CT generator and extraction
followed. Finished 2026-09-14T14:30Z (about 26 minutes of agent time before the suspension, 25 after). Per-scope
seconds below. Disk: `df -g ~` 32 GB free at start, 31 GB at the end (stop
line 5 GB, never approached).
Impact analysis: not run; the GitNexus MCP tools were not available in this session (not in the tool list). The only
code change is in one generator script, `scripts/build_tanf_state_policy_manual_manifests.py` (three new builders,
one static-table entry, one flag); no library function was modified.

Four scopes; three of them swap a released scope, one is an addition:

| Jurisdiction | Scope | Documents | Provision rows | Extract s | Replaces |
| --- | --- | ---: | ---: | ---: | --- |
| us-ct | `us-ct/policy/2026-09-14-tanf-manual-whole` | 1,565 | 3,131 | 577 | `us-ct/policy/2026-07-02-ct-ssp-upm-and-standards` (28 rows) |
| us-ga | `us-ga/manual/2026-09-14-tanf-manual-whole` | 101 | 1,168 | 18 | `us-ga/manual/2026-06-25-ga-tanf` (47 rows) |
| us-de | `us-de/regulation/2026-09-14-tanf-manual-whole` | 1 | 133 | 2 | nothing (addition; DSSM 4000 stays in `2026-07-03-de-tanf-rules`) |
| us-md | `us-md/regulation/2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated` | 2 source scopes | 58 | 3 (consolidation) | `...title-07-subtitle-03-chapters-06-07` (30 rows) |
| us-az | none | 0 | 0 | - | blocked (below); released FAA5 slices unchanged |

Every extracted scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths, and no
document is a single undivided body: the CT UPM is one document per section (the publisher's own granularity), the GA
manual splits on the pages' heading tags (block rows, 10-12 per page on average), DSSM 3000 splits on its 132 labelled
sections, COMAR keeps its regulation rows. Extraction command for the three TANF scopes, run from the worktree:

```bash
export REQUESTS_CA_BUNDLE=$(uv run python -c "import certifi;print(certifi.where())")
for m in us-de us-ga us-ct; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --version 2026-09-14-tanf-manual-whole \
    --manifest manifests/$m-tanf-state-policy-manual.yaml --source-as-of 2026-09-14
done
```

`--source-as-of 2026-09-14`; `--expression-date` was never passed: every CT document's `expression_date` is the
transmittal date printed in its own header, every GA page's is the page's "Effective Date" line (98 pages) or the HTTP
Last-Modified date where the line has no year (3 pages), DSSM 3000 uses the source date as the released DSSM 4000
scope did (the PDF prints no consolidated effective date; its ModDate is 2025-03-03 and every amended section carries
its own "NN DE Reg. NNNN (mm/dd/yy)" history line in the body).

## Publisher access (2026-09-14T01:10Z to 01:20Z, plain extractor client unless stated)

- `portal.ct.gov` (CT DSS): the Uniform Policy Manual listing `dss/lists/uniform-policy-manual` and its nine chapter
  listing pages (`.../upm0---table-of-contents` to `.../upm8---special-programs-saga-jobs-first-program`, paginated
  `?page=N`, 2 to 23 pages each) answered HTTP 200; every `.doc`/`.docx` media file answered HTTP 200 with
  `application/msword` / the OOXML type. The top-level listing mixes the UPM documents with 266 policy transmittals
  (a different family, not taken); the chapter pages list UPM documents only. TLS intact, no impersonation. The host
  is slow at times (about 3.8 s per document during the first generator pass at 01:20-02:00Z, 0.4-0.7 s at 14:10Z)
  and answered one of 1,564 requests with a read timeout; the retry succeeded.
- `pamms.dhs.ga.gov` (GA DFCS PAMMS): HTTP 200, 173 KB index, content, and every section page HTTP 200. The earlier
  European-network failures of this host did not recur (cf. the 2026-09-13 CCDF re-probe of `decal.ga.gov`).
- `regulations.delaware.gov`: the AdminCode pages are a single-page application (65,540-byte shell for every URL);
  the document API `POST /api/AdminCode/regulation {"RegulationUrl": "/AdminCode/title16/3000"}` (the method of the
  released DSSM 4000 and Medicaid DSSM scopes) answered HTTP 200 with `regulationName` "3000 Technical Eligibility for
  Cash Assistance" and `pdfId` ebbded60-25b1-4945-a8d0-366813270452; `GET /api/AdminCode/title16/3000/<pdfId>` served
  the 978,234-byte, 44-page PDF (HEAD answers 405, as before).
- `dbmefaapolicy.azdes.gov` (AZ DES FAA manual): probed once each way at 2026-09-14T01:16Z. Plain extractor client:
  HTTP 403, 5,611 B, Cloudflare "Just a moment" challenge, `cf-mitigated: challenge`. Browser-impersonated client
  (curl_cffi `chrome120`, the legitimate fallback for fingerprint-only walls): HTTP 403, 6,038 B, the same challenge.
  This is the wall the 2026-09-13 re-probe (`docs/ingest-runs/2026-09-13-blocked-publishers-reprobe.md`) met from the
  third request on; today it answers from the first request. Nothing was worked around, no archived copy was used
  (the 2025-10-30 FAA5 manifest's `web.archive.org` download URLs are a July pattern that the current rules forbid
  for new scopes), and no AZ scope was built. Recorded on the AZ queue row; the 13 AZ cells stay EXTRACTABLE-blocked.
- No TLS chain was broken anywhere; nothing was added to `data/certs/` and `REQUESTS_CA_BUNDLE` pointed at certifi
  only. No mirror, repost, proxy or archived copy was used.

## Method

All three manifests come from `scripts/build_tanf_state_policy_manual_manifests.py` (whole-manual pass: `BATCH_6`,
`WHOLE_VERSION`, builders `build_ct`, `build_ga`, `build_de`; CT, GA and DE leave the generator's static `DONE` table,
AZ stays in it with the probe recorded). The queue rows are therefore written by the jurisdiction's builder, as the
rules require, and `--only us-ga --only us-de` then `--only us-ct --only us-az` rebuilt exactly those rows (the queue
diff was read row by row: the four rows plus `status_counts`; the federal row's 2026-09-13 eCFR sentence, which the
CFR branch had written into the queue directly, is now carried by the generator's federal notes so re-runs keep it).

- **CT.** The nine chapter listing pages list 1,564 UPM documents (1,560 `.doc`, 4 `.docx`): policy sections
  (`4005_05`), procedure documents (`1005_10P`) and a handful of irregular labels (`4500Appendix`, `8035_05Pfk`,
  `8040_Pfk`, `8055_`, `2540_74p`, `3099_05p`). Citation path `us-ct/policy/dss/upm/<label>` with `_` read as `.` and
  lower-cased (`4005.05`, `1005.10p`, `4500appendix`, `8055`), which reproduces the released scope's thirteen paths
  exactly; the builder refuses a path collision (none occurred). The publisher's listing shows only the label, so the
  generator downloads each document once (eight at a time with retries: the host serves a document in 0.4-4 s
  depending on the hour and dropped one request with a 120 s read timeout on the first, serial attempt), converts it
  with `textutil` (the converter the extractor itself uses for `.doc`) and reads the transmittal header: `Date:` (the
  `expression_date`; 1,529 of 1,564 documents print one, range 1986-10-01 to 2026-09-14, the other 35 fall back to
  the source date), `Transmittal:`, the Section/Chapter/Subject grid (the title: the Subject, or for chapter-level
  documents the Chapter or Section name, "UPM 6000 - Calculation of Benefits" as in July; table-of-contents documents
  print no grid and take their first text line; 23 stay bare, e.g. `0300.15`-`0300.90`), the POLICY/PROCEDURES
  type (1,009 policy, 509 procedures, 46 unmarked) and the program column (AABD, MA, FS, TFA...). The headers are
  cached in a scratch JSON keyed by media URL and Sitecore `rev` (`--ct-header-cache`). `source_url` is the media URL
  without the `?rev=` query, as in the July manifest; the
  revision is kept in metadata. The DSS Program Standards Chart effective 2026-01-01 (`us-ct/policy/dss/program-standards/2026-01-01`,
  still served, 279,237 B) is carried into the new scope from the superseded one so that the swap loses nothing.
  `document_class` stays `policy`: the citation-path prefix must equal `<jurisdiction>/<document_class>/`
  (`_validate_citation_path`), so the paths rulespec-us cites can only survive under the class the July scope used.
- **GA.** The manual navigation on `pamms.dhs.ga.gov/dfcs/tanf/` lists 101 pages (sections 1001-1915 at depth 2,
  appendices A-H at depth 1 and the three Appendix B pages); each is taken with the same `article.doc` selector and
  the same citation shape as the superseded scope, so the four pages already released come out block-for-block
  identical (checked byte by byte, below). `document_class` `manual`, as before.
- **DE.** DSSM 3000 as one labelled-section PDF under `us-de/regulation/title-16/3000-technical-eligibility-for-cash-assistance`,
  the DSSM 4000 pattern re-labelled for the 3000 series (heading charset widened for `&`, `:`, `[Repealed]` and the
  curly apostrophe of "Delaware's"; the page-1 document title line "3000 Technical Eligibility for Cash Assistance"
  added to `drop_lines` so that it does not compete with section 3000 "Defining Delaware's TANF Program" for the
  label). 133 rows = 1 document root + 132 sections; three sections are heading-only containers whose text is in
  their children (3008, 3010.2, 3033), every other section carries text (min 139 characters). One cosmetic defect:
  the heading of 3032.2 prints as "Eligibility For Other Programs A." because the PDF puts the first list marker on
  the heading line; the body is intact. `document_class` `regulation` (Delaware Administrative Code, the released
  4000 precedent). The queue row's 2026-09-10 claim "DSSM 3000 already ingested" was wrong (the released
  `2026-07-03-de-tanf-rules` carries 4000 Financial Responsibility only, 41 rows) and is corrected; 4000 stays where
  it is, so this scope is an addition and no us-de scope is swapped.

## Swaps with cited-path checks

Released scopes are immutable; the controller swaps the selector. For each swap, every citation path of the released
scope was looked up in the successor and every path `rulespec-us` cites (grep of `~/rulespec-us` for
`<jurisdiction>/<class>/...`) was checked too; bodies were compared byte by byte.

| Released scope | Successor | Released rows carried | Bodies | rulespec-us cited paths |
| --- | --- | --- | --- | --- |
| `us-ct/policy/2026-07-02-ct-ssp-upm-and-standards` (13 UPM sections + chart, 28 rows) | `us-ct/policy/2026-09-14-tanf-manual-whole` | 28 of 28 | 28 byte-equal (the thirteen July documents are unchanged on the publisher's site) | 10 paths (`upm/4005.10/block-1`, `program-standards/2026-01-01/page-1`, `upm/5045.10/block-1`, `5050.13`, `5030.15`, `4520.10`, `6005`, `5030.10`, `5520.10`, `4520.20`, each `/block-1`): all present |
| `us-ga/manual/2026-06-25-ga-tanf` (1525, 1605, 1615, Appendix A; 47 rows) | `us-ga/manual/2026-09-14-tanf-manual-whole` | 47 of 47 | 47 byte-equal | 8 paths (`1615/block-5`, `1615/block-6`, `1605/block-3`, `-4`, `-6`, `-14`, `appendix-a`, `appendix-a/block-2`, `-3`): all present |
| `us-md/regulation/...chapters-06-07` (30 rows) | `...chapters-06-07-r2026-09-14-chapter-03-consolidated` | 30 of 30 | 30 byte-equal | 1 path (`title-07/subtitle-03/chapter-03`, from the chapter-03 source): present |

Collision scan: the successor's citation paths were intersected with every same-jurisdiction scope of
`manifests/releases/us-rulespec-2026-09-13-federal-and-plans-union.json` read from the corpus root (us-ct 14 scopes,
us-ga 16, us-de 12, us-md 13). CT collides only with the swapped UPM scope (all 28 of its paths; the CT SNAP manual,
Medicaid, CHIP, WIC and state-plan scopes carry no `us-ct/policy/dss/...` path), GA only with the swapped
`2026-06-25-ga-tanf` (47 paths), DE with nothing (the SNAP rules scope holds DSSM 9000 paths, the CHIP scope 18000,
the released TANF scope 4000), MD only with the swapped `chapters-06-07` (30 paths). The `us-ga/guidance/2026-06-25-ga-tanf`
scope is a different document class and stays.

## Maryland COMAR 07.03 consolidation

The MD COMAR adapter emits the shared container rows `us-md/regulation`, `us-md/regulation/title-07` and
`us-md/regulation/title-07/subtitle-03` in every scope it builds, which is why the July chapter-03 (Family Investment
Program, TCA) scope `us-md/regulation/2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03`
(31 rows, complete, on disk in the corpus root) was held out of every release once the SSI chapters 06-07 scope was
consolidated on 2026-09-11. Same mechanism and command shape as the 2026-09-11 and July precedents, the released scope
first:

```bash
uv run python scripts/consolidate_release_scopes.py --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07 \
  --source-version 2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated
```

Row arithmetic: 30 (chapters 06-07, released) + 31 (chapter 03) - 3 shared structural containers (byte-identical,
body-less, folded once) = 58 rows: 3 containers, 3 chapter rows (03, 06, 07), 26 + 10 + 15 = 51 regulation rows.
Coverage `complete: true`, 58 of 58 matched, no duplicate citation path; every row of both sources is present with a
byte-equal body; the sources directory carries both source scopes' files under the target version (the script's
`sources/<jur>/<class>/<target>/<source-version>/...` layout); no `--prefer-duplicate-carrier` was needed because the
two sources share no text-bearing path. The two inputs stay on disk for provenance and are not selected.

## Decisions

1. **Document class follows the citation-path prefix, not a blanket `manual`.** CT keeps `policy`, DE `regulation`,
   GA `manual`: the extractor requires `citation_path` to start with `<jurisdiction>/<document_class>/`, and the
   supersession rule (every cited path of the old scope must exist in the new one) can only hold under the old class.
   The version string `2026-09-14-tanf-manual-whole` is shared by the three scopes, as the order asked.
2. **CT takes the whole UPM, all programs.** The UPM is one manual for TFA, SNAP, Medicaid, SAGA and State Supplement;
   the closure check's 28 CT cells are TANF, but the publisher posts the manual as one indexed set and a program slice
   would recreate the "slice taken" gap for the other programs' checks. Procedure documents (`P` labels, 521) are
   taken with the policy sections because the listing does not distinguish them and encoders cite both.
3. **The CT standards chart rides along.** It is not a UPM document, but dropping the July scope would otherwise
   un-serve `us-ct/policy/dss/program-standards/2026-01-01/page-1`, which rulespec-us cites 20 times.
4. **DE is an addition, not a swap.** The order's "correct that row" is a queue-text correction; the released 4000
   scope is right as far as it goes, so it stays selected and 3000 is added next to it.
5. **AZ: one probe each way, then stop.** The reprobe note's Cloudflare wall is confirmed; the FAA5 slice scopes
   (`2025-10-30-az-des-faa5-manual-r2026-07-15-self-contained`, `2026-07-17-faa5-recovery`, `2026-07-12-az-des-faa6-utility-amounts`)
   stay as released. A whole FAA1-FAA6 scope, when the wall lifts, will collide with all three (they carry
   `us-az/manual/des/faa5/...` and `.../faa6/...` paths) and will need the consolidation route or a three-scope swap.
6. **MD target version** follows the order (`<released chapters-06-07 version>-r2026-09-14-chapter-03-consolidated`),
   long as it is; the `-rYYYY-MM-DD-...` suffix is the July/2026-09-11 re-version convention.

## Verification

- Coverage files re-read from the corpus root for the four scopes: `complete: true`, counts as tabled.
- Queue rows vs coverage on disk: CT/GA/DE `target_scope` versions and `taken_count` equal the coverage
  `source_file_count`/document counts; AZ row unchanged except the probe note.
- Draft selector `docs/ingest-runs/2026-09-14-tanf-whole-md-comar.selector.json` (the released 2026-09-13
  federal-and-plans union, 761 scopes, with the three swaps applied and DE added: 762 scopes; kept outside
  `manifests/releases/` because CI deep-validates every tracked selector against the checked-in `data/corpus`),
  validated from the worktree with `validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus
  --ignore-r2-missing --max-issues 50` in 41 s: `ok: true`, 0 errors, 546 warnings, all the pre-existing
  `missing_parent_id` warnings of `us-ca/regulation/2026-07-13-recovery`; no cross-scope citation-path collision.
- CT rows: 1,565 document roots and 1,566 text rows (one `block-1` per `.doc`, heading blocks for the four `.docx`,
  one page row for the chart); no empty block body (min 473 characters, median 1,783, max 104,262); every document
  has a text row; the extractor reported no warning.
- `uv run ruff check .`: passes. Focused tests
  `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or tanf or consolidat or comar"`
  (the `--extra dev` is needed: without it `uv run pytest` falls through to the machine's anaconda pytest and every
  module fails to import): 319 passed, 2 skipped, 19 failed, run twice (before and after the CT header-parser
  fix) with the identical failure set. Every failure is a `FileNotFoundError`/`KeyError` on another scope's
  `data/corpus` artifact that the sparse checkout does not hold, the set the earlier sparse-worktree notes list plus
  the tests the `tanf`/`consolidat` terms add: `test_armenia_arlis`, `test_be_rulespec_2026_08_23_promotion`,
  `test_build_ny_tanf_compatibility_scope` (x6), `test_israel_openlaw` (x2), `test_rulespec_be_source_promotion`,
  `test_state_snap_manual_queue::test_massachusetts_consolidation_drops_shadowed_legacy_blocks`,
  `test_us_rulespec_2026_07_22_release::test_consolidated_title_7_scope_is_the_unique_input_union` and the AK, CT,
  MI, MT, ND, NY SNAP manual tests. None touches the generator, the new manifests or the queue.

## Controller

Selector swaps (released scope out, successor in) and one addition. Artifacts are unsigned, on the controller's disk
under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`, not committed.

| Action | jurisdiction / document_class / version |
| --- | --- |
| swap out | us-ct / policy / 2026-07-02-ct-ssp-upm-and-standards |
| swap in | us-ct / policy / 2026-09-14-tanf-manual-whole |
| swap out | us-ga / manual / 2026-06-25-ga-tanf |
| swap in | us-ga / manual / 2026-09-14-tanf-manual-whole |
| swap out | us-md / regulation / 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07 |
| swap in | us-md / regulation / 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated |
| add | us-de / regulation / 2026-09-14-tanf-manual-whole |
| no change | us-az (blocked; FAA5/FAA6 slice scopes stay released) |

Remaining steps are the controller's: `sign-ingest-manifest` for the four scopes, apply the swaps to the next union
selector, re-validate, sign, publish, activate. The three superseded scopes and the two MD inputs stay on disk and in
history only.

Rebuild:

```bash
cd ~/axiom-corpus-worktrees/tanf-whole
export REQUESTS_CA_BUNDLE=$(uv run python -c "import certifi;print(certifi.where())")
uv run python scripts/build_tanf_state_policy_manual_manifests.py --only us-ga --only us-de
uv run python scripts/build_tanf_state_policy_manual_manifests.py --only us-ct --only us-az \
  --ct-header-cache /tmp/ct_upm_headers.json      # about 20 minutes without the cache
for m in us-de us-ga us-ct; do
  s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --version 2026-09-14-tanf-manual-whole \
    --manifest manifests/$m-tanf-state-policy-manual.yaml --source-as-of 2026-09-14
  echo "elapsed_seconds=$(( $(date +%s) - s )) manifest=$m"
done
uv run python scripts/consolidate_release_scopes.py --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07 \
  --source-version 2026-07-03-md-tca-comar-publication-2026-06-29-title-07-subtitle-03-chapter-03 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-consolidated
uv run axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release docs/ingest-runs/2026-09-14-tanf-whole-md-comar.selector.json --ignore-r2-missing --max-issues 50
```
