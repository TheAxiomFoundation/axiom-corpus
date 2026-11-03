# CCDF FFY 2025-2027 state plans: ACF index relocation repair and blocked-row re-probe (w8)

Date: 2026-10-20. Program: CCDF (`manifests/ccdf-agent-queue.yaml`).
Worktree `~/axiom-corpus-worktrees/w8-ccdf-index`, branch `discovery/ingest-w8-ccdf-index` cut from main 393127f8b.
Extraction wrote to the main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`); nothing
under `data/corpus/` is committed, nothing is signed, nothing was pushed.

Earlier notes: `2026-09-10-ccdf-state-plans-fy2025-2027.md`, `...-retry.md`, `...-retry-2.md` (the three plan runs),
`2026-09-13-blocked-publishers-reprobe.md`, and - decisive for this run - `2026-10-12-w7-state-benefits.md` and
`2026-10-12-w7-federal.md`.

Timing: started_at 2026-10-20T18:52:25Z, finished_at 2026-10-20T19:25:40Z, wall time 33 min 15 s (1,995 s).
Per-jurisdiction extraction seconds: us-in 246.69 s; us-mo 9.48 s (extracted, then withdrawn, see judgment 4).

GitNexus MCP tools were unavailable in this session, so no impact analysis was run. No library function under `src/`
was changed.

## Result in one paragraph

The ACF index did not retire, it moved: `/occ/form/approved-ccdf-plans-fy-2025-2027` became
`/occ/data/approved-ccdf-plans-fy-2025-2027` on ACF's own host, with the same table and the same 56 rows. The dead
address was rewritten in 113 files (the queue plus 112 manifests, 388 + 116 occurrences) and the index re-inventoried.
Of the eleven target rows, one is newly extracted (Indiana), two are re-classified as already held from the wave-7 run
(Maryland and Missouri - Maryland was never really blocked), four stay blocked (AS, AZ, MP, NY) and four stay
needs_review (us, AK, PR, VI).

## 1. Duplicate-work check (CLAUDE.md)

- `gh search issues "CCDF" --repo TheAxiomFoundation/axiom-corpus --state open` -> one hit, #111 "Ingest Georgia CAPS
  sources for RuleSpec encoding" (2026-06-19). Georgia CAPS is a state subsidy-program family, not an ACF-118 plan row;
  it does not cover any row here.
- `gh search prs "ccdf" --repo TheAxiomFoundation/axiom-corpus --state open` -> no hits.
- `gh pr list --state open --json number,title,headRefName` -> 30 open PRs; none touches
  `manifests/ccdf-agent-queue.yaml` and none names a CCDF plan row. No row was skipped for duplication.

The check that *did* bite is a data-level one the issue and PR search cannot see: wave 7 had already taken Maryland and
Missouri plan text into the corpus on 2026-10-12. See judgments 3 and 4.

## 2. Index relocation: evidence

The dead address, both hosts, browser User-Agent, following redirects:

| URL | Result |
| --- | --- |
| `https://acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027` | HTTP 404, 17,601-byte "Page not found" body |
| `https://acf.hhs.gov/occ/form/approved-ccdf-plans-fy-2025-2027` | 301 to `acf.gov`, then the same HTTP 404 |

The live address was reached only through ACF's own pages, never a search engine or a third party:

1. `https://acf.gov/occ` (Office of Child Care landing page) - HTTP 200, 72,719 bytes. Its body links
   `/occ/programs-services/child-care-and-development-fund/resources/plans`.
2. `https://acf.gov/occ/programs-services/child-care-and-development-fund/resources/plans` ("Child Care and Development
   Fund Program Plans") - HTTP 200, 59,133 bytes. Its FY 2025-2027 entry links `/occ/data/approved-ccdf-plans-fy-2025-2027`,
   and its FFY 2022-2024 entry links `/archive/occ/data/approved-ccdf-plans-fy-2022-2024`: ACF moved both cycles out of
   the `form` content type into `data`.
3. **Accepted: `https://acf.gov/occ/data/approved-ccdf-plans-fy-2025-2027`** - HTTP 200, 77,630 bytes,
   `text/html`, `<title>FY 2025-2027 State/Territory CCDF Plans | The Administration for Children and Families</title>`.
   `acf.hhs.gov` and `www.acf.hhs.gov` on the `/occ/data/` path both 301 to it, so `INDEX_LEAD` moves with it.

Four independent checks that this is the same index, not a lookalike:

4. **Same structure.** One `<table class="table">`, a header row `STATE/TERRITORY | LINK TO FY 2025-2027 PLAN |
   APPENDIX` and 56 jurisdiction rows. The generator's existing `fetch_index()` parses it unchanged and returns 56 rows
   whose codes equal `set(RESOLUTIONS)` exactly.
5. **Same documents.** 56 Lead Agency / plan links and 51 ACF-hosted Appendix PDFs under
   `acf.gov/sites/default/files/documents/occ/` (the five territories without an Appendix are AS, GU, MP, PR, VI).
   Every one of the 56 queue rows' `index_plan_link` and `index_appendix_url` matches the relocated page exactly, after
   normalising only a trailing slash, the Connecticut `%C2%A0` artifact and `http`/`https`. `repair_dead_index_refs()`
   asserts this before it writes anything.
6. **ACF's own corroboration inside this repo.** The wave-7 federal run already found this on 2026-10-12 and recorded
   it: `manifests/us-federal-guidance-w7-federal.yaml` ingests `https://acf.gov/occ/data/approved-ccdf-plans-fy-2025-2027`
   as `us/guidance/acf/occ/approved-ccdf-plans-fy-2025-2027`, with an `access_note` saying the `/occ/form/` address
   "now answers HTTP 404 ... ACF's own search names this page (same title, published 2024-12-19) at acf.gov/occ/data/".
   Two runs converged on the same URL by different routes.
7. **Not a third-party copy.** The accepted URL is on `acf.gov`, the publisher's own apex host, reached by two clicks
   from `acf.gov/occ`. No mirror, repost, proxy or archived copy was used anywhere in this run.

ACF's site search (`https://acf.gov/search?search=approved+CCDF+plans+FY+2025-2027`) answers HTTP 200 but renders its
results client-side, so it yielded no server-side link; it was not needed, given the landing-page chain above.

## 3. Index inventory (relocated page, read 2026-10-20)

Body links only; the footnote anchor, the Lead Agency contact page, `mailto:OCCIT@icf.com`, the `/occ` breadcrumb, the
three topic tags and the Facebook/LinkedIn/X share links are site furniture and excluded.

| Family | Count | Taken this run |
| --- | ---: | ---: |
| Lead Agency plan links (one per jurisdiction; 4 are a direct PDF, 52 are a publisher page) | 56 | 1 (us-in) |
| ACF-hosted `*-ACF118-CCDF-FFY-2025-2027-Appendix.pdf` / `*-Appendix-ACF-118-...pdf` | 51 | 0 (taken 2026-09-13 as its own family) |
| Preprint instructions on the index | 0 | 0 |
| Amendments on the index | 0 | 0 (publishers post them on their own pages) |
| **Total document links** | **107** | **1** |

Per-row `index_document_count` after repair: 2 for the 51 jurisdictions with an Appendix, 1 for AS, GU, MP, PR and VI,
and 107 on the federal `us` row (56 + 51), which is the whole-index count that row has always carried.

### Publisher-page inventories for the rows that changed

**Indiana**, `https://www.in.gov/fssa/carefinder/information-and-resources2/` (HTTP 200, 61,866 bytes): 11 document
links, 11 distinct - the same count as the 2026-09-10 review, but the plan file is a different one.

| Family | Count | Taken |
| --- | ---: | ---: |
| CCDF plan FFY 2025-2027: "CCDF state plan 2025-2027" = `ACF-118-CCDF-FY2025-2027-IN-Amend3.pdf` | 1 | 1 |
| Public comment final summary; waiver request | 2 | 0 |
| CAP documents (Indiana CAP plan, CAP communication plan, CAP quarterly update) | 3 | 0 |
| ACF letters (conditional approval 12.18.18, equal access 2.5.19, CAP letter, CAP conditional approval, amendment letter 5.6.19) | 5 | 0 |

The certified 2024-06-30 file the first three runs rejected as non-conforming
(`in.gov/dA/ce627c931e/ACF-118-CCDF-FY2025-2027-IN.pdf?language_id=1`) is **no longer linked** from this page.

**Missouri**, `https://dese.mo.gov/childhood/child-care-subsidy/child-care-dev-fund` (HTTP 200, 81,536 bytes): 53
document links, 53 distinct.

| Family | Count | Taken |
| --- | ---: | ---: |
| CCDF plan FFY 2025-2027: Initial Plan, Amendment #1, Amendment #2, "Current" Amendment #3 | 4 | 0 (already held, judgment 4) |
| FFY 2025-2027 waiver; waiver update on CCDF rule changes | 2 | 0 |
| Earlier CCDF plans (2022-2024 plan and Amendments #1-#2; 2019-2021; 2016-2018; 2014-2015; 2012-2013) | 7 | 0 |
| CCDF webinars (Nov 2024, Feb 2025, May 2025); federal funding and program-integrity fact sheet | 4 | 0 |
| ACF-218 Quality Progress Reports FFY 2022-2024 | 3 | 0 |
| ACF-696 grant-award financial reports (grant years 2302-2602, quarterly) | 25 | 0 |
| Market rate survey reports 2014, 2016, 2018, 2022, 2024 and the MRS FAQ | 6 | 0 |
| Child care serious injury and death report 2025 and its flyer | 2 | 0 |

**Maryland**, `https://earlychildhood.marylandpublicschools.org/about/ccdf-state-plan` (HTTP 200, 117,402 bytes): 7
document or plan-page links in the body.

| Family | Count | Taken |
| --- | ---: | ---: |
| 2025-2027 CCDF State Plan: the `/2025-2027-ccdf-plan` page (HTTP 403) | 1 | 0 (already held, judgment 3) |
| 2022-2024 CCDF State Plan page | 1 | 0 |
| Earlier plans and minutes (2018, 2019, 2016-2018, 2014-15 plans; 2016 minutes; 2013 comment summary) | 6 | 0 |

The plan **file** is reachable on the same host outside that 403 page: `/system/files/filedepot/12/
acf-118_ccdf_ffy_2025-2027_plan_approved_updated_6.25.25_amendment_request_1.pdf` answers HTTP 200,
`application/pdf`, 3,053,686 bytes, to the plain client.

**Alaska** (1 attachment, the 2024-05-24 draft), **Puerto Rico** (draft folder only), **Virgin Islands** (FFY
2019-2021 preprint draft only) and **American Samoa** (plain-HTTP site, no document links at all) are unchanged from
the 2026-09-11 territories pass; the per-row notes carry the detail.

## 4. Re-probe method

One pass per address: the plain `requests` client with a Chrome 120 browser User-Agent, then `curl_cffi`
`impersonate="chrome120"`, 25 s each, `REQUESTS_CA_BUNDLE` = certifi plus every committed `data/certs/*.pem`
intermediate. **TLS verification was never disabled and no new certificate was needed**; no proxy, mirror, repost or
archived copy was used; no bot challenge was solved or worked around.

Reachability was judged **from the response body, never from the status line**. Every 200 was parsed and its document
links listed before the row was classified, and every candidate PDF was downloaded and its text layer read. This
mattered twice: `ocfs.ny.gov` answers HTTP 200 with a 6,653-byte F5/Shape TSPD JavaScript challenge and an otherwise
empty body, and `dese.mo.gov/media/pdf/...` answers HTTP 200 with `text/html` rather than the PDF it names. Neither is
reachable content. No row here was classified on a status code alone, so no host needed re-classification on that
ground - but Maryland *was* re-classified for the related reason that the earlier passes probed only its HTML page and
never its file (judgment 3).

Neither new manifest sets `browser_impersonation` or any other `request` option: Indiana's plan PDF and Maryland's
answer the plain extractor client directly.

| Row | Address probed | Plain client | curl_cffi chrome120 | Outcome |
| --- | --- | --- | --- | --- |
| AS | `https://www.dhss.as/index.html` | SSLCertVerificationError, self-signed cert | curl 60, no local issuer | blocked, unchanged |
| AS | `http://dhss.as/index.html` | 200, 13,265 B, no document links in the body | 200, same | no plan posted |
| AZ | `des.az.gov/.../child-care-and-development-fund-state-plan` | 403, 5,946 B, Cloudflare "Just a moment..." | 403, 6,224 B, same | blocked, unchanged |
| MD | `.../about/ccdf-state-plan` | 200, 117,402 B, links only the 403 page | 200, 117,401 B | page block real |
| MD | `.../2025-2027-ccdf-plan` | 403, 107,562 B, cloudflare "Access denied" | 403, 107,560 B | page block real |
| MD | `.../filedepot/12/acf-118_ccdf_ffy_2025-2027_plan_approved_updated_6.25.25_amendment_request_1.pdf` | **200, application/pdf, 3,053,686 B** | not needed | **file retrievable** |
| MO | `dese.mo.gov/childhood/child-care-subsidy/child-care-dev-fund` | 200, 81,536 B, full plan family listed | 200, same | **block lifted** |
| MO | `dese.mo.gov/media/pdf/acf-118-ccdf-ffy-2025-2027-missouri` | 200 but `text/html`, 52,893 B (publisher's PDF-viewer page) | 200, same | viewer page, not the file |
| MO | `dese.mo.gov/sites/g/files/zuston521/files/media/pdf/2024/11/ACF-118 CCDF FFY 2025-2027 For Missouri_0.pdf` | **200, application/pdf, 2,756,462 B**, Last-Modified 2024-11-12 | not needed | **file retrievable** |
| NY | `ocfs.ny.gov/main/childcare/stateplan/` | 200 but a 6,653-B TSPD challenge, empty body | 200, 6,650 B, same | blocked, unchanged |
| MP | `https://www.childcare.gov.mp/` | 403, 358 B, nginx "403 Forbidden" | 403, same | blocked, unchanged |
| AK | `aws.state.ak.us/OnlinePublicNotices/Notices/View.aspx?id=215530` | 200, 39,797 B, one draft attachment | 200, same | needs_review, unchanged |
| IN | `in.gov/fssa/carefinder/information-and-resources2/` | 200, 61,866 B, **new Amendment 3 file** | 200, same | **extracted** |
| IN | `in.gov/fssa/uploads/ACF-118-CCDF-FY2025-2027-IN-Amend3.pdf` | **200, application/pdf, 119,271,642 B**, Last-Modified 2026-09-29 | not needed | **extracted** |
| PR | `www.acuden.pr.gov/documentos` | 200, 88,674 B, draft folder only | 200, same | needs_review, unchanged |
| VI | `https://dhs.vi.gov/` | 200, 153,741 B, FFY 2019-2021 preprint only | 200, same | needs_review, unchanged |

in.gov truncates the 113 MB Indiana PDF on a single stream (two attempts stopped at 98.9 MB and 102.3 MB of
119,271,642). `curl --retry 3 --retry-all-errors` completed it, and the extractor's own fetch completed it too; the
retained file's SHA-256 matches the inventory and `Content-Length`.

## 5. Per-row outcome

| Row | Before | After | Documents | Provisions | What happened |
| --- | --- | --- | ---: | ---: | --- |
| us (federal) | needs_review | needs_review | 0 | 0 | index reference repaired; 45 CFR 98 still belongs to its own `extract-ecfr` run |
| us-ak | needs_review | needs_review | 0 | 0 | only the 2024-05-24 public-comment draft is posted |
| us-as | blocked_primary_source | blocked_primary_source | 0 | 0 | self-signed expired cert on https; the http site posts no plan |
| us-az | blocked_primary_source | blocked_primary_source | 0 | 0 | Cloudflare challenge, both clients |
| us-in (plan) | needs_review | **agent_ready** | 1 | **42** | **Amendment 3 newly posted and extracted** |
| us-in (manual) | needs_review | needs_review | 0 | 0 | separate FSSA manual family, untouched |
| us-md | blocked_primary_source | **needs_review** | 0 | 0 | **re-classified**: plan file retrievable, text already held (judgment 3) |
| us-mo | blocked_primary_source | **needs_review** | 0 | 0 | **block lifted**, but text already held (judgment 4) |
| us-mp | blocked_primary_source | blocked_primary_source | 0 | 0 | nginx 403, both clients |
| us-ny | blocked_primary_source | blocked_primary_source | 0 | 0 | F5/Shape TSPD challenge body on a 200 |
| us-pr | needs_review | needs_review | 0 | 0 | only the "Borrador" (draft) plan is posted |
| us-vi | needs_review | needs_review | 0 | 0 | only the FFY 2019-2021 preprint draft is posted |
| 49 other rows | agent_ready | agent_ready | - | - | index reference repaired only; no scope or manifest content changed |

`status_counts` before: `agent_ready 48, blocked_primary_source 6, needs_review 6` (60 rows).
`status_counts` after: **`agent_ready 49, blocked_primary_source 4, needs_review 7`** (60 rows).
Reconciliation: Indiana's plan row needs_review -> agent_ready (+1 / -1); Maryland and Missouri
blocked_primary_source -> needs_review (-2 / +2). 49 + 4 + 7 = 60.

## 6. Extraction and verification (us-in)

`2026-10-20-w8-ccdf-plan-fy2025-2027`, `--source-as-of 2026-10-20`, `--expression-date 2024-10-01`,
`document_class policy`, citation root `us-in/policy/acf/ccdf-plan/fy2025-2027`, 41 second-level subsections plus the
document root = 42 provisions. All conventions unchanged from the 2026-09-10 runs.

| Jurisdiction | Version | Plan Status (CARS) | Pages | Source bytes | Seconds | Provisions | Chars | Coverage |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| us-in | Amendment 3 | Approved as of 2026-07-01 | 243 | 119,271,642 | 246.69 | 42 | 664,270 | complete, 0 / 0 / 0 |

Checks read from the artifacts, not from the CLI output:

- `coverage.complete: true`; `provision_count` 42; `matched_count` 42 of `source_count` 42; `missing_from_provisions`,
  `extra_provisions`, `duplicate_provision_citations` and `duplicate_source_citations` all empty.
- 42 rows and 42 distinct `citation_path` values in the provisions JSONL; no internal duplicate.
- **Cross-scope uniqueness:** the 42 paths were compared against all 15 other provisions JSONL files under
  `data/corpus/provisions/us-in/` - no collision. A corpus-wide scan for `/acf/ccdf-plan/` found held plan text in
  five jurisdictions only (us-ca, us-il, us-md, us-mo, us-in); Indiana's is this run's.
- Body text: the 41 section bodies are all non-empty, smallest 1,682 characters. The document root body is empty, which
  is the family convention - the held `us-ca/policy/2026-09-10-ccdf-plan-fy2025-2027` root is empty too.
- The single inventoried source file is a regular, non-symlink file under
  `sources/us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027/official-documents/`, its SHA-256 equals the inventory
  value, its size equals the publisher's `Content-Length`, and every provision's `source_path` is that one file.

## 7. Reviewer judgments

1. **The index moved, it was not retired.** The accepted URL is `https://acf.gov/occ/data/approved-ccdf-plans-fy-2025-2027`,
   reached by two clicks from `acf.gov/occ`. Section 2 lists seven pieces of evidence, including that all 56 rows' plan
   and Appendix links match exactly and that the wave-7 federal run independently ingested the same URL eight days
   earlier. `fetch_index()` was not changed; it parses the relocated page as-is.
2. **The repair is a reference rewrite, not a re-triage.** `repair_dead_index_refs()` substitutes the two exact dead
   strings in `manifests/*.yaml`, so the diff of each of the 112 untouched manifests is only `central_index_url`,
   `publisher_index_url` and `discovered_via`; no scope version, no source URL and no extraction option changed. It
   refuses to write if the relocated page's 56 rows or any row's links differ.
3. **Maryland was never fully blocked, and its plan text is already held.** The row was marked
   `blocked_primary_source` on the strength of the `/2025-2027-ccdf-plan` HTML page, which does still answer HTTP 403.
   But the plan PDF sits on the same publisher host at a `filedepot` path and answers HTTP 200, `application/pdf`,
   3,053,686 bytes, to the plain client - and the wave-7 state-benefits run of 2026-10-12 already extracted it
   (Amendment 1, approved 2025-06-24) to the same 42 citation paths under
   `us-md/policy/2026-10-12-w7-state-benefits-policy-md`. I did not extract it again. The row moves to `needs_review`
   with both facts recorded and a `ccdf_plan_text_held_elsewhere` family naming the held scope. A reviewer should decide
   whether this row retires into the wave-7 scope. The HTML-page 403 stays recorded because it is real.
4. **Missouri's block is lifted, but its plan text is already held, so the extraction was withdrawn.** The DESE page
   now answers 200 and lists the whole plan family, and the Initial Plan is retrievable: its `/media/pdf/...` address
   is the publisher's own PDF-viewer page (still `text/html`) and that viewer's file endpoint on the same host answers
   `application/pdf`, 2,756,462 bytes - the Idaho `ElectronicFile.aspx` precedent (retry-2 judgment 4), the publisher's
   own URL, no mirror and no challenge bypassed. I extracted it (42 provisions, coverage complete, 9.48 s), then the
   mandated cross-scope uniqueness check found **all 42 citation paths already present** in
   `us-mo/policy/2026-10-12-w7-state-benefits-policy-mo`, where wave 7 took Missouri Amendment 2 (approved 2026-03-26).
   Amendment 2 is the later approved version, so taking the Initial Plan would have duplicated the paths with older
   text. **I removed the whole 2026-10-20 us-mo scope** (sources, inventory, provisions, coverage) and its manifest, and
   recorded the collision on the row. A reviewer should decide whether the row retires into the wave-7 scope or whether
   the Initial Plan belongs at a dated sibling path, as PR #823 does for Idaho and wave 7 does for Illinois
   Amendment 2.
5. **Indiana is taken as Amendment 3 under the MN and LA precedent.** The carefinder page now posts
   `ACF-118-CCDF-FY2025-2027-IN-Amend3.pdf` (approved 2026-07-01) and no longer links the certified 2024-06-30
   submission that the first three runs rejected. It is the only FFY 2025-2027 version the Lead Agency posts, which is
   exactly the Minnesota Amendment 3 and Louisiana Amendment 1 case in retry-2 judgment 2. `expression_date` stays
   2024-10-01.
6. **`IN_EXTRACTION` is a new manifest-level pattern; no extractor function changed.** Indiana's Amendment 3 is a
   "Microsoft: Print To PDF" render, so 39 of the 41 labels sit alone on a line with the heading on the next one (the
   California form) while 10.1 and 10.2 keep both on one line. The plan also appends Indiana's child care statutes,
   whose "8.5 Child abuse or neglect reporting", "3.5 IN-HOME CARE", "12.5 Safe sleeping practices" and "17.2 Sec. 37"
   lines reuse the preprint label form - the Vermont collision. `IN_EXTRACTION` therefore combines `CA_EXTRACTION` with
   the Vermont heading whitelist on both heading positions. Measured on the retained PDF: the unrestricted CARS pattern
   matches 7 lines (6 unique labels); the California form matches 46 (44 unique, 5 of them statute lines);
   `IN_EXTRACTION` yields exactly 41 sections plus the root, 0 extra, 0 duplicate. The wrapped 2.4 heading is completed
   by the existing `heading_continuation_pattern`. `VT_EXTRACTION` was left byte-identical on purpose, so the Vermont
   manifest does not move; `PREPRINT_HEADING_ALT` is a new constant it does not use.
7. **`refresh_plan_rows()` is new because `--only` cannot address Indiana's plan row.** `refresh_rows_only()` keys rows
   by `jurisdiction`, and the queue holds two rows whose jurisdiction is `us-in` (the ACF-118 plan and the FSSA policy
   manual), so the dict comprehension silently keeps the manual row and `--only in` would have edited the wrong row.
   The new function selects by `target_manifest` and fails loudly unless exactly one row matches. This is a latent bug
   in `refresh_rows_only()`; it never fired, because no earlier pass ran `--only in`. I did not change that function -
   a reviewer may want to fix or retire it separately.
8. **A full generator run is still unsafe and was not used.** `main()` with no `--only` rebuilds `queue["states"]` from
   the index and would drop every row's `additional_families` (appendix, amendments, rate schedules, wave-6 bundles) and
   reset every `target_scope.version` to the run date. Both passes here are narrow: `--repair-index` then
   `--only-plan-rows`. The queue round-trips byte-identically through `yaml.safe_dump` with the committed settings,
   which was verified before the first write.
9. **Three dead references are deliberately left in place.** `manifests/ccdf-agent-queue.yaml` keeps the old address
   once, as `index_inventory.relocated_from`. `manifests/us-federal-guidance-w7-federal.yaml` and
   `manifests/program-bundles/joins.yaml` keep `https://www.acf.hhs.gov/occ/form/...` because that is the wave-7
   *bundle work-order address* and its join key, already annotated there as dead and already pointing at the
   `/occ/data/` successor. Rewriting a recorded work-order address would falsify that run's record.
10. **New scope version, and why.** Everything extracted here is under `2026-10-20-w8-ccdf-plan-fy2025-2027`, kept
    apart from `2026-09-10-ccdf-plan-fy2025-2027` (44 scopes) and `2026-09-13-ccdf-plan-fy2025-2027` (GA, TX), because
    it is a distinct dated pass against a relocated index with its own evidence, and because the 2026-09-10 scopes are
    still awaiting `sign-ingest-manifest`. Only us-in uses it; the withdrawn us-mo scope left nothing behind.
11. **The coordinator's mid-run corrections were applied and changed nothing in substance.** Point by point:
    - *Judge reachability from the body, not the status line.* Already done for every address. New York's HTTP 200
      carries a 6,653-byte F5/Shape TSPD challenge and an empty body, and was classified blocked on that basis - the
      same finding the parallel agent reported for `otda.ny.gov`. Missouri's `/media/pdf/...` HTTP 200 is `text/html`,
      not the PDF it names, and was not treated as the file.
    - *Read the body even on an apparent success.* For every 200 the document links were enumerated before the row was
      classified, which is what catches the "No documents found" class of trap: American Samoa's plain-HTTP site
      answers 200 with 13,265 bytes and **no document link at all**, so it is recorded as "no plan posted", not as a
      working index. Alaska, Puerto Rico and the Virgin Islands answer 200 and were classified on what their bodies
      list, not on the status.
    - *Challenge markers, and the band starting near 5 KB.* Classification used the approved markers - "Just a
      moment..." for Arizona and Maryland, the TSPD `noscript` support-ID line for New York - never body size and never
      "challenge-platform". Arizona's bodies are 5,946 and 6,224 bytes, inside the corrected band either way.
    - *Set `browser_impersonation` where a Cloudflare challenge body appears.* Checked directly, and it would not help
      here. `request: browser_impersonation: true` resolves to `OFFICIAL_DOCUMENT_BROWSER_IMPERSONATION = "chrome120"`
      (`src/axiom_corpus/corpus/documents.py:54`) and fetches through curl_cffi with the matching Chrome User-Agent
      (`_browser_impersonation_headers`, lines 465-480) - which is exactly the second probe this run already ran
      against every blocked address. Arizona returns the Cloudflare challenge to it (403, 6,224 bytes) and Maryland's
      `/2025-2027-ccdf-plan` returns "Access denied" to it (403, 107,560 bytes), so the option is not warranted on
      either row, and the evidence recorded is stronger than a plain-path-only probe. No `browser_impersonation` was
      added anywhere: Indiana's and Maryland's plan PDFs answer the plain extractor client.
    - *Do not apply the small-body rule to an API response.* Not applicable; no address here is a JSON API.
    - *Test trap.* It did occur. The first baseline used Anaconda's pytest and died with
      `ModuleNotFoundError: No module named 'axiom_corpus'` (exit 3); the second exited early (exit 2) on 68,059
      locked corpus files. Neither was read as a pass - exit codes were captured alongside the output for exactly this
      reason. The accepted baseline and the final run both used `--extra dev` and `AXIOM_CORPUS_PARTIAL_TESTS=1`, give
      18 failed / 341 passed / 2 skipped, matching the coordinator's figure, and were compared as sorted `FAILED`
      lists rather than counts.

    The one host re-classified in this run is Maryland, for an unrelated reason (judgment 3).
12. **GitNexus MCP tools were unavailable**, so no impact analysis was run, and no function under `src/` was modified.
    The diff to the generator touches the module docstring; the `INDEX` and `INDEX_LEAD` constants; nine new constants
    (`DEAD_INDEX`, `DEAD_INDEX_LEAD`, `INDEX_LANDING`, `W8_STAMP`, `W8_SCOPE`, `W8_DURABLE`, `PREPRINT_HEADING_ALT`,
    `IN_EXTRACTION`, `W7_HELD`); ten `RESOLUTIONS` entries; one hardcoded index literal inside `ready_row_fields()`
    that would otherwise have re-introduced the dead URL on every future rebuild; and two new functions
    (`refresh_plan_rows`, `repair_dead_index_refs`) with their two CLI flags. No existing function's behaviour was
    changed apart from that one literal.

## 8. Artifacts

Committed:

- `docs/ingest-runs/2026-10-20-w8-ccdf-index-repair.md` (this note)
- `manifests/us-in-ccdf-state-plan-fy2025-2027.yaml` (new)
- `manifests/ccdf-agent-queue.yaml` (index repair, re-inventory, 10 rows refreshed, 2 held-elsewhere families)
- 112 `manifests/us-*-ccdf-state-plan*.yaml` (index address only)
- `scripts/build_ccdf_state_plan_manifests.py`

Not committed: no certificate changed (`data/certs/ccdf-ca-bundle.pem` is generated and gitignored, as before), and
nothing under `data/corpus/` - unsigned and uncommitted, in the shared root
`/Users/pavelmakarchuk/axiom-corpus/data/corpus`:

- `sources/us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027/official-documents/us-in-acf-ccdf-plan-fy2025-2027.pdf`
- `inventory/us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027.json`
- `provisions/us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027.jsonl`
- `coverage/us-in/policy/2026-10-20-w8-ccdf-plan-fy2025-2027.json`

## 9. Rebuild

```bash
# 1. repair the dead index address and re-inventory the relocated page
uv run python scripts/build_ccdf_state_plan_manifests.py --repair-index

# 2. refresh the eleven target rows (writes manifests/us-in-ccdf-state-plan-fy2025-2027.yaml)
uv run python scripts/build_ccdf_state_plan_manifests.py --only-plan-rows ak,as,az,in,md,mo,mp,ny,pr,vi

# 3. extract Indiana
export REQUESTS_CA_BUNDLE=$PWD/data/certs/ccdf-ca-bundle.pem
uv run axiom-corpus-ingest extract-official-documents \
  --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --version 2026-10-20-w8-ccdf-plan-fy2025-2027 \
  --manifest manifests/us-in-ccdf-state-plan-fy2025-2027.yaml \
  --source-as-of 2026-10-20 --expression-date 2024-10-01
```

`data/certs/ccdf-ca-bundle.pem` is written by the generator's `ca_bundle()` (certifi plus the committed Sectigo
intermediate) and is gitignored.

## 10. Lint and tests

`uv run ruff check scripts/build_ccdf_state_plan_manifests.py` -> **All checks passed!**

`AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or
official_documents or discovery"`:

| Pass | Result |
| --- | --- |
| Baseline, before the first edit | 18 failed, 341 passed, 2 skipped, 7,241 deselected (92.89 s) |
| Final, after every edit | 18 failed, 341 passed, 2 skipped, 7,241 deselected (77.43 s) |

The sorted `FAILED` lists are identical: **no new failure, none fixed**. All 18 are pre-existing sparse-worktree
`data/corpus` absences and touch no CCDF code or manifest (Armenia ARLIS, BE rulespec promotion, BE source promotion,
NY TANF compatibility x2, Wisconsin PIT recovery, Israel OpenLaw, SC Act 110, AK/CT/MI/MT/ND/NY SNAP manuals, four
`us_snap_child_support_state_sources` cases).

Note for future runs: without `--extra dev` the worktree venv has no pytest and `uv run pytest` silently falls through
to Anaconda's, which fails at collection with `ModuleNotFoundError: No module named 'axiom_corpus'`. Without
`AXIOM_CORPUS_PARTIAL_TESTS=1` the suite exits early on 68,059 locked corpus files that this sparse checkout lacks.

## 11. Remaining work

- **Reviewer decisions**, in priority order: whether the Maryland and Missouri plan rows retire into their wave-7
  scopes or get dated sibling paths for the versions wave 7 did not take (judgments 3 and 4); whether
  `refresh_rows_only()`'s `us-in` key collision is fixed or the function retired (judgment 7); whether `main()`'s
  destructive full-rebuild path is guarded (judgment 8).
- **Still blocked, exact failures:** AS (self-signed expired `CN=cmaster70` on https; the plain-HTTP site posts no
  plan), AZ (Cloudflare 403, both clients), MP (nginx 403, 358-byte body, both clients), NY (F5/Shape TSPD JavaScript
  challenge body on an HTTP 200). All four need the publishers' cooperation; all four are recorded as durable over
  three dates.
- **Still needs_review for want of a conforming plan:** AK, PR and VI need their Lead Agency to post an approved or
  certified FFY 2025-2027 ACF-118 rather than a draft or an older cycle. The federal `us` row still needs 45 CFR 98
  through `extract-ecfr --only-title 45 --only-part 98`, and the Indiana FSSA policy-manual row still waits on the
  plan family being complete.
- **Controller:** `sign-ingest-manifest` for the us-in scope, and the still-unsigned 2026-09-10 and 2026-09-13 plan
  scopes; then an immutable release selector, `publish_corpus.py --dry-run`, publish.
- A corpus-wide sweep for other scopes that already hold `*/policy/acf/ccdf-plan/*` paths would be worth running before
  any further CCDF plan extraction: this run found two such collisions by checking, and the queue does not record them.
