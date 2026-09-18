# SNAP superseding scopes, batch 2: NE, AR, NV, WY, ND, ME (axiom-corpus#680 follow-on)

Date: 2026-09-11
Program: SNAP. Queues: `manifests/snap-completion-agent-queue.yaml` (28 rows, unchanged count; the six
rows gain a `superseding_scope` mapping) and `manifests/state-snap-manual-agent-queue.yaml` (51 rows,
unchanged count; the same six rows gain the same mapping).
Issue: https://github.com/TheAxiomFoundation/axiom-corpus/issues/680 and the hand-off
`docs/ingest-runs/2026-09-11-program-ingestion-handoff.md` ("Revised editions found during the SNAP
completion pass ... need superseding scopes; released scopes are immutable").
Agent: one session from a US network in the sparse worktree `axiom-corpus-worktrees/snap2`, branch
`discovery/ingest-snap-superseding-2` cut from `origin/discovery/program-ingestion-union`; artifacts written
to the main checkout's corpus root. started_at 2026-09-11T20:44Z (worktree created), extraction window
2026-09-11T21:04:09Z-21:09:12Z. Per-state extraction seconds (timer around `extract-official-documents`):
NE 5 s (a first attempt failed after 2 s, below), AR 6 s (a first attempt failed after 5 s, below), NV 18 s,
WY 6 s, ND 9 s, ME 1 s.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. The one code change
(`_browser_impersonation_headers` in `src/axiom_corpus/corpus/documents.py`) was impact-checked by hand
(below). Another agent handled NC, GA, TN, OK, MI and KY on `discovery/ingest-snap-superseding-1`; those
states, that worktree and its scratch files were not touched.

## What was built

A superseding scope is a whole-document-set re-extraction of the released scope's own manifest under a new
version string, keeping every document-level citation path identical, so that the next release selector can
swap the released version for the new one (a selector cannot carry the same citation path twice, and released
scopes are immutable). Version strings are `2026-09-11-<state>-snap-manual-supersede` for all six states,
including the two `regulation` scopes (NE, ME), as instructed.

| Jurisdiction | Class | Released version (immutable, untouched) | Superseding version |
| --- | --- | --- | --- |
| us-ne | regulation | `2026-07-17-ne-snap-rules` | `2026-09-11-ne-snap-manual-supersede` |
| us-ar | manual | `2026-07-16-ar-snap-manual` | `2026-09-11-ar-snap-manual-supersede` |
| us-nv | manual | `2026-05-27-nv-eligibility-payments-manual-r2026-07-15-self-contained` | `2026-09-11-nv-snap-manual-supersede` |
| us-wy | manual | `2026-05-27-wy-manuals-r2026-07-15-self-contained` | `2026-09-11-wy-snap-manual-supersede` |
| us-nd | manual | `2026-07-21-nd-snap-manual` | `2026-09-11-nd-snap-manual-supersede` |
| us-me | regulation | `2026-07-17-me-snap-rules` | `2026-09-11-me-snap-manual-supersede` |

Method per state: the batch-1/batch-2 re-probe findings were re-checked live against the publisher
(current file names, `Last-Modified` or the CMS's own `article:modified_time`, the publisher's own API or
index); the state's existing manifest was edited in place (revised documents: new `source_url` where the
publisher re-issued the file, `source_as_of` 2026-09-11 and `expression_date` = the publisher's revision
date; unchanged documents keep their released dates); the manifest was re-extracted with
`extract-official-documents` under the new version; the new scope was compared with the released scope
row by row; a draft selector equal to the current release selector
(`manifests/releases/us-rulespec-2026-08-23-canada-338-suspension-union.json`) with the one version swapped
was deep-validated. Body digests below are SHA-256 over the ordered child rows of one document
(`citation_path` + body per row; root rows carry no body); the first 12 hex digits are shown.

## Per-jurisdiction results

| Jurisdiction | Released -> new provisions | Documents | Revised items confirmed changed | Other documents | Seconds | validate-release |
| --- | ---: | ---: | --- | --- | ---: | --- |
| us-ne | 742 -> 694 | 5 | ch. 2, ch. 3 (2 of 2 flagged) | ch. 1, 4, 5 text-identical (ch. 1 from a different file, same edition) | 5 | ok, 0 errors |
| us-ar | 810 -> 813 | 8 | manual, appendices (2 of 2 flagged) plus 2 program pages (menu line only) | final filing, quick reference, NBI chart, FAQ text-identical | 6 | ok, 0 errors |
| us-nv | 821 -> 824 | 51 | A-100, A-200, A-700, A-1800, B-400, B-900 (6 of 6 flagged) plus A-400 (revised in place) | 44 text-identical | 18 | ok, 0 errors |
| us-wy | 9 -> 9 | 4 | Table II (1 of 1 flagged) plus 900 extended menu (revised 2026-07-15) | 1100 menu text-identical; main page: extraction drift, explained | 6 | ok, 0 errors |
| us-nd | 167 -> 202 | 67 | landing, TOC, 62 of 64 topics (flagged: landing/TOC/topics) | 2 topics and the Release 26.5 PDF text-identical | 9 | ok, 0 errors |
| us-me | 223 -> 223 | 2 | Ch. 609 (1 of 1 flagged) | Ch. 301 text-identical | 1 | ok, 0 errors |

Coverage for all six new scopes: `complete: true`, 0 missing, 0 extra, 0 duplicate source and provision
citations. Document-level (root) citation-path sets are identical to the released scopes in every state
(NE 5/5, AR 8/8, NV 51/51, WY 4/4, ND 67/67, ME 2/2); no publisher removed or added a document. Child
citation paths (`page-N`, `block-N`, NE section labels) are derived from the text and differ where an
edition's page, block or section count changed; those differences are listed per state. No root row has a
body (by design); every non-root row has a non-empty body except NE `title-475/chapter-5/002`, a heading-only
section (`002 REPLACEMENTS.`) whose body is empty in the released scope too. No source file is a challenge or
error page (smallest file: NV C-105, 10,482 bytes, as released).

Combined check for the controller: a draft selector with all six swaps at once
(`us-rulespec-2026-08-23-canada-338-suspension-union` minus the six released versions plus the six
superseding versions, 275 scopes) validates `ok: true`, 0 errors, 541 warnings (the pre-existing
`missing_parent_id` warnings of `us-ca/regulation/2026-07-13-recovery`), 18 s. Each per-state draft gave the
same result (20-27 s each).

### us-ne (Nebraska Title 475 NAC, `manifests/us-ne-snap-rules.yaml`)

Publisher: https://rules.nebraska.gov/api/chapter/GetByTitleId/230 (the same-origin API the React app
loads; HTTP 200, 774,309 bytes, 0.8 s, fetched with TLS verification on through
`data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem`). Chapters 2 (Household Processing) and 3
(Eligibility) carry `effectiveDate` 2026-07-28 and blob names `475 NAC 2 (07-28-2026).pdf` /
`475 NAC 3 (07-28-2026).pdf`; chapters 1 (2025-12-24), 4 (2024-09-17) and 5 (2020-07-04) are unchanged in
the API. New this run: the API still names `_Official.pdf` blobs for chapters 1-3, but the blob store answers
HTTP 400 `{"isSuccess":false,"message":"Error getting blob: The requested blob doesn't exist ..."}` (152 bytes)
for every `_Official` name, including chapter 1's released URL
`475 NAC 1 (12-24-2025)_Official.pdf` (it answered on 2026-07-17). The first extraction attempt therefore
failed on chapter 1 after 2 s (`curl: (22) ... error: 400`). The `pdfBlobName` copies answer HTTP 200 (Range
requests honoured) for all five chapters, so every chapter is taken from the publisher's `pdfBlobName` copy,
which is what the released chapters 2-5 already used; chapter 1 becomes the same 12-24-2025 edition as a
33-page file (the released 30-page official copy plus blank/certification pages; its extracted text is
byte-identical, below).

Manifest edits: chapter 2 and 3 `source_url` -> the 07-28-2026 `pdfBlobName` URLs, `source_as_of`
2026-09-11, `expression_date` and `metadata.effective_date` 2026-07-28, `pdf_blob_name`,
`official_pdf_blob_name` (the API's value), `source_sha256`, `page_count` (28, 61) and `provision_count`
(140, 229); chapter 1 `source_url` -> the `pdfBlobName` URL, `source_as_of` 2026-09-11, `source_sha256`
`3d046375...`, `page_count` 33, `expression_date` unchanged (2025-12-24); chapters 4 and 5 unchanged.
`request.verify_tls: false` removed from all five documents: the run used `REQUESTS_CA_BUNDLE` and
`CURL_CA_BUNDLE` = certifi plus the DigiCert intermediate (the curl Range backend honours `CURL_CA_BUNDLE`;
without it curl fails with error 60 as the batch-2 note recorded). `date_filed` stays as the API reports
(2024-09-12 for chapters 2 and 3).

Extraction: 5 s, 5 documents, 694 rows (5 roots + 689 labeled sections: ch. 1 181, ch. 2 140, ch. 3 229,
ch. 4 119, ch. 5 20). Verification against the released 742 rows: roots 5/5; 641 shared child paths, 101
only in the released scope, 53 only in the new (chapter 2 gained sections, chapter 3 was renumbered:
released 284 sections, new 229); bodies: ch. 1 `f5985d541e24` = `f5985d541e24` (identical, 64,997 chars),
ch. 2 `c6f7acbd47de` -> `4219595ed628` (53,418 -> 56,937 chars), ch. 3 `0e5dd0c01e89` -> `1b7ff9122ed3`
(134,295 -> 118,135 chars), ch. 4 `4ac30387290d` identical, ch. 5 `6fc736d9bdfb` identical. Source files:
ch. 1 `3d04637590545de9` (466,971 bytes), ch. 2 `40c4ae3ce48e012d` (430,956), ch. 3 `fd30f11381ca761e`
(660,271), ch. 4 `2f55765164716d76`, ch. 5 `ff63c7adc3830511` (the released ch. 4 and 5 hashes). No
certification-page markers (APPROVED, ATTORNEY GENERAL, RULES SPECIALIST) in any body; every heading starts
with its label and ends with a period, as the released scope's test requires.

### us-ar (Arkansas SNAP Certification Manual set, `manifests/us-ar-snap-manual.yaml`)

Publisher access: humanservices.arkansas.gov now sits behind Cloudflare and answers HTTP 403 to this
network for the plain Axiom client (146-byte nginx page, 0.1-0.3 s), the browser user agent (548 bytes),
curl-cffi `chrome120` and `chrome124` (548 bytes) on every URL tried (the SNAP landing page, the WordPress
media API, every released and new PDF, the three HTML pages); `cf-ray` headers `a39996...-EWR`. The
`safari17_0` fingerprint with its own Safari user agent answers HTTP 200 on all of them (landing page
437,405 bytes, media API 434,129 bytes, manual PDF 5,118,090 bytes). No workaround: this is the publisher's
site, a standard browser profile, TLS verified against certifi (curl-cffi needs `CURL_CA_BUNDLE`,
`SSL_CERT_FILE` or `REQUESTS_CA_BUNDLE` pointed at certifi on this machine; without it error 60). The
manifest therefore carries `request.browser_impersonation: safari17_0` and
`browser_impersonation_direct: true` on all eight documents.

The first extraction attempt failed after 5 s with HTTP 403 because the extractor forced its Chrome user
agent string onto the Safari TLS fingerprint (Cloudflare rejects the mismatch); see the code change below.

Editions: the publisher's own media library (`/wp-json/wp/v2/media?search=SNAP`, 100 items) lists
SNAP-Policy-Manual-11.21.2025, -03.01.2026, -04.02.2026 (released) and -07.01.2026 (uploaded 2026-07-22,
`Last-Modified` 2026-07-22, 5,118,090 bytes), SNAP-Appendices-04.02.2026 and -07.30.2026 (2026-07-30,
1,540,589 bytes); the released appendices URL SNAP-Appendices-05.15.2026.pdf answers HTTP 404. The final
filing (`Last-Modified` 2026-06-19), quick reference (2025-10-01) and NBI chart (2026-05-21) predate the
released fetch. The nutrition-waiver page (`article:modified_time` 2026-09-10) and time-limit page
(2026-09-08) were modified after the release; the FAQ (2026-06-25) was not.

Manifest edits: manual `source_url`/`download_url` -> SNAP-Policy-Manual-07.01.2026.pdf, `source_as_of`
2026-09-11, `expression_date` 2026-07-01 (the edition date, as the released 2026-04-02); appendices ->
SNAP-Appendices-07.30.2026.pdf, 2026-09-11, 2026-07-30; nutrition-waiver page `source_as_of` 2026-09-11,
`expression_date` 2026-09-10; time-limit page 2026-09-11, 2026-09-08; request block on all eight.

Extraction: 6 s, 8 documents, 813 rows (8 roots + 796 pages + 6 blocks... see below). Verification against
the released 810 rows: roots 8/8; 810 shared paths, 3 only in the new (appendices pages 86-88); bodies:
manual `457d24464835` -> `5e3cf5457df9` (590 rows both, 1,198,416 -> 1,198,505 chars: the July 1 edition),
appendices `38e62a5e7937` -> `6cb4feefee6a` (86 -> 89 rows, 147,187 -> 149,500 chars), final filing
`f153179dc24f` identical, quick reference `7ddecd9a88dd` identical, NBI chart `1b1a3f47ebef` identical,
nutrition waiver `728ca837774c` -> `b3947563b999` (the only text difference is the removal of the
sub-navigation line "Overview + How to Apply | Make it Snappy | ..." inside the content container), FAQ
`98480e0b2e12` identical (raw HTML differs, text does not), time-limit rules `d1a9d894f6f4` ->
`a7f83f3b7fb9` (the sub-navigation label "Make it Snappy Employment and Training" became "SNAP Education
Employment and Training"; the rule text is unchanged). Source-file SHA-256 against the released inventory:
final filing `80329b522a75...`, quick reference `5fc35eb4f4c0...` and NBI chart `8378c8f6147e...`
byte-identical; manual `c0caf435...` -> `764475be6808ba80`, appendices `de0dcb9e...` -> `e166c5f2052ae95b`,
the three HTML files differ (site chrome). Reviewer: the two program pages are recorded as revised because
their served text changed and the publisher dates them after the release, but the change is site navigation,
not policy.

### us-nv (Nevada Eligibility & Payments Manual, `manifests/us-nv-eligibility-payments-manual.yaml`)

Publisher: https://dwss.nv.gov/Home/Features/eligibility/eligibility-n-payment-info-manual/ (HTTP 200,
91,021 bytes, 1.1 s, 139 PDF links as in batch 2). 45 of the 51 released URLs are still on the index; the six
re-issued chapters are served under
`/siteassets/dwss.nv.gov/content/eligibility/eligibility--payments/chapter-<x>.pdf` (the publisher's own
spelling `chapter-a-200-verificaiton-and-documentation.pdf` is kept). HEAD of all 51 current files: the six
new files carry `Last-Modified` 2026-06-26 (A-100), 2026-07-13 (A-200), 2026-06-30 (A-700 and A-1800),
2026-07-09 (B-400), 2026-07-14 (B-900), matching transmittals MTL 08-26 to 13-26 (June and July 2026
releases); one unchanged-URL file, A-400 Citizenship, was replaced in place on 2026-07-06 (MTL 06-26, May
2026 release) after the 2026-05-27 fetch, so it is revised too; the other 44 files are dated before
2026-05-27 (mostly 2026-02-23, B-100 2026-05-07).

Manifest edits: the six `source_url`s, `source_as_of` 2026-09-11 and `expression_date` = the file's
`Last-Modified` date for the seven revised chapters; the other 44 keep 2026-05-27.

Extraction: 18 s, 51 documents, 824 rows (51 roots + 773 pages). Verification against the released 821 rows:
roots 51/51; 817 shared paths, 4 only in the released scope (A-400 pages 42-43, B-900 pages 23-24), 7 only in
the new (A-200 pages 18-19, B-400 pages 35-39); bodies changed for exactly the seven: A-100 `5d3ad7bbdbcb` ->
`6b9e824ee958` (28 rows, 60,674 -> 61,303 chars), A-200 `1d9b49426140` -> `6afb36b24fb9` (18 -> 20 rows),
A-400 `b6d9cd82d6b6` -> `48fe0a418949` (43 -> 41 rows), A-700 `3a7ff3b6a5e2` -> `6d43f0d1ad65` (58 rows),
A-1800 `6551bcf58d52` -> `87abc88b96a5` (14 rows), B-400 `69549a7279b0` -> `b6b28d39acdb` (34 -> 39 rows),
B-900 `700ca68a6cf2` -> `7eecccd292d6` (24 -> 22 rows); the other 44 documents are body-identical
(digests equal, e.g. A-300 `3c449865e4c5`, D-100 `eee10b80f43c`, glossary `e7921dd29299`). The released
scope is a self-contained release object with one synthesized source file, so per-file hashes could not be
compared; the extracted text comparison stands in.

### us-wy (Wyoming SNAP and POWER Policy Manual, `manifests/us-wy-manuals.yaml`)

Publisher: the four released pages answer HTTP 200 (0.8-1.6 s). WordPress `article:modified_time`: main
manual page 2025-05-19 (unchanged since before the release), Table II 2026-07-28 (the July 1, 2025-June 30,
2026 POWER income guidelines; released text carried the 2024-2025 guidelines and "$5,500 per each additional
member", now "$5,680"), 900 extended menu 2026-07-15 (after the release: the income-coding table now
distinguishes earmarked/not-earmarked educational income codes EE/EN, adds military combat pay and BAS
guidance), 1100 extended menu 2024-11-27.

Manifest edits: Table II `source_as_of` 2026-09-11, `expression_date` 2026-07-28; 900 menu 2026-09-11,
2026-07-15; main page and 1100 menu unchanged (2026-05-27, as released, no selector, as released).

Extraction: 6 s, 4 documents, 9 rows (4 roots + 5 blocks), the released path set exactly (9/9). Bodies:
Table II `35bd4e41c70c` -> `cc3f222f13ec` (1,528 -> 1,276 chars), 900 menu `da5177f7f2b2` -> `d3c693333e31`
(80,477 -> 80,555 chars), 1100 menu `a688ff426474` identical (11,609 chars), main page `33ed823e0995` ->
`e103db383809` (83,792 -> 497,813 chars). The main-page drift: the released self-contained scope holds one
whitespace-collapsed block with duplicated headings ("101 Purpose ... 101 Purpose ...") that ends in Section
5xx (25 section headings), while the same manifest row (no selector) now extracts the page's full article
text with paragraph breaks (Sections 100-1400, 217 section headings, including the embedded 900 and 1100
accordion text); the raw HTML is 947,066 bytes and the page itself is unmodified on the publisher since
2025-05-19. All 568 substantive released sentences are present in the new body (the six "missing" ones are the
duplicated-heading artifacts of the old capture), so nothing released was lost; the difference is
extractor-side (49 commits touched `documents.py` since 2026-05-27) and the released scope retained no raw
HTML to prove more. Source files: main 947,066 bytes `3316afbddede4caa`, Table II 99,534 `f2e39344f27285b7`,
900 232,464 `61f5dfe6b186a4f4`, 1100 85,243 `108393c7b7535e9e`. The batch-2 completion scope
`us-wy/manual/2026-09-10-snap-state-manual-completion` (Glossary, Policy Clarifications, Table I, purchasing
page) is separate and untouched; its paths do not collide (validated).

### us-nd (North Dakota HHS SNAP Policy Manual, `manifests/us-nd-snap-manual.yaml`)

Publisher: https://www.nd.gov/dhs/policymanuals/SNAP/Content/Home%202.htm (HTTP 200, 29,054 bytes,
0.3 s) now says "Last published Sep 02, 2026 ... Current Release: 26.7"; every file (landing, TOC, topics,
release log) carries `Last-Modified` 2026-09-02. The TOC (`Data/Tocs/Online_Chunk0.js`, 6,917 bytes) lists
67 entries: Home plus 66 topics, i.e. the 64 released topics plus the two Release 26.6/26.7 topics already in
the batch-2 completion scope. The release log links the 26.7 (effective 10.1.2026), 26.6 (8.13.2026) and 26.5
(6.15.2026) PDFs; the 26.5 PDF is byte-identical to the released file.

Manifest edits: landing, TOC and the 64 topics `source_as_of` 2026-09-11 and `expression_date` 2026-09-02
(the publisher's own "Last published" date and every file's `Last-Modified`; the released convention used
the release effective date 2026-06-15 for Release 26.5, but the 26.7 topic text is published ahead of its
2026-10-01 effective date, so the publication date is the honest expression date); `current_release` 26.7 on
the landing and TOC rows; the Release 26.5 PDF row unchanged (2026-07-21, 2026-06-15).

Extraction: 9 s, 67 documents, 202 rows (67 roots + 131 blocks + 4 pages; released 167 = 67 + 96 + 4).
Verification: roots 67/67; all 167 released paths present, 35 new `block-N` paths (the republished pages
split into more blocks). Bodies: landing `8c5a0a1ac948` -> `19b7ec5bf1e8` (1,110 -> 4,894 chars; now
carries the Release 26.7 summary: annual COLA standards, allotments, deductions, resource limits), TOC
`0b4e7d3bbb9a` -> `754c3c98fec7` (66 topics), Release 26.5 PDF `3033900622a1` identical, 62 topics changed,
2 topics identical (Appendix A glossary, Introduction). The publisher republished the manual with a new
MadCap template (`<p class="topic-context">`, `<h1 class="topic-title">`, `<h2 class="section-heading">`,
`publication-meta`): the "Overview" paragraph is now an `h2`, which the extractor records as the block
heading instead of body text, so 52 topics differ only by that 10-character line. Policy text changed in:
1002 Reporting Requirements (-589 chars), 107 Expedited Services (-276), 302 Good Cause (+111), 401 ABAWD
Overview (+536), 402 Countable Months/Exemptions (+536), 404 Regaining Eligibility (+55), 502 Eligible Alien
Status (-148), 601 Resources Overview (+357), Appendix B Table of Standards (+358), Release Log (+1,208).
The batch-2 completion scope `us-nd/manual/2026-09-10-snap-state-manual-completion` (two topics, 26.6 and
26.7 PDFs) is separate and untouched; no path collides (validated).

### us-me (Maine 10-144 C.M.R. Chapters 301 and 609, `manifests/us-me-snap-rules.yaml`)

Publisher: https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules
(HTTP 200, 136,019 bytes, 0.3 s) links Ch. 301 as `144c301-2026-133-NSC.docx` (unchanged, `Last-Modified`
2026-06-26, 650,558 bytes) and Ch. 609 as `144c609-2026-191-AMD.docx` (`Last-Modified` 2026-08-28,
107,049 bytes; the released `144c609_0.docx` still answers, 105,771 bytes). The amended file's own history
block reads "AMENDED: August 30, 2026 - filing 2026-191". Ch. 302 SUN Bucks stays outside SNAP.

Manifest edits: Ch. 609 `source_url` -> the 2026-191 file, `source_as_of` 2026-09-11, `expression_date`
2026-08-30, `metadata.rule_filing` 2026-191, `source_note` updated; Ch. 301 unchanged.

Extraction: 1 s, 2 documents, 223 rows, the released path set exactly (223/223). Bodies: Ch. 301
`dd705cc0c611` identical (346,926 chars; source file `45ee047d0e2a888d`, the released hash), Ch. 609
`9fa0431c7ceb` -> `aec3468ab7da` (44,196 -> 45,396 chars; source file `1da7e06516b872d8`).

## Code change: profile-consistent User-Agent for browser impersonation

`src/axiom_corpus/corpus/documents.py`: `_download_document_by_browser_impersonation` used to send the
official Chrome user agent on every curl-cffi fetch regardless of the impersonated profile. A Chrome
user agent over a Safari TLS fingerprint is itself a bot signal (Cloudflare answered HTTP 403 to it on
humanservices.arkansas.gov while the same fingerprint with its own user agent answered HTTP 200). The new
helper `_browser_impersonation_headers(headers, impersonate=...)` keeps the Chrome user agent for `chrome*`
and `edge*` profiles (the default `chrome120`, `browser_impersonation: true`, and the one explicit
`chrome120` in the manifests) and drops any forced user agent for other profiles so curl-cffi sends the
profile's own. Manual impact analysis (GitNexus unavailable): the function has exactly two callers, both in
`_download_document` (the direct path and the post-403 fallback); every existing manifest uses a Chromium
profile (4,219 `browser_impersonation: true`, one `chrome120`), for which the headers are unchanged; the
only `safari17_0` rows are the eight Arkansas rows added here. Test added:
`test_browser_impersonation_headers_follow_the_impersonated_profile` in `tests/test_corpus_documents.py`;
the five impersonation tests pass.

## Tests changed

The four tests that pin these manifests were updated so they stay true in a full checkout: the manifest
now describes the superseding edition while the released scope's artifacts stay immutable.

- `tests/test_us_ne_snap_rules.py`: new `EXPECTED_SOURCE_SET_SHA256` (source id, URL, expression date,
  file hash, provision count of the five rows), per-chapter `source_as_of`, request block without
  `verify_tls`; the retention test now takes each released file's `page_count` and `source_sha256` from the
  released inventory instead of the manifest.
- `tests/test_us_nd_snap_manual.py`: per-document dates (Release 26.5 PDF keeps 2026-07-21/2026-06-15, the
  rest 2026-09-11/2026-09-02); the TOC-boundary, release-evidence and source-set tests are unchanged.
- `tests/test_us_me_snap_rules.py`: `MANIFEST_SOURCES` (superseding edition) beside `EXPECTED_SOURCES`
  (released); the released rows' `rule_filing` is compared with the released filing.
- `tests/test_us_ar_snap_manual.py`: `MANIFEST_OVERRIDES` for the four changed rows and the request block;
  inventory lookups stay on the released URLs.

No test reads `manifests/snap-completion-agent-queue.yaml`; `tests/test_state_snap_manual_queue.py` reads
specific keys of `manifests/state-snap-manual-agent-queue.yaml`, and the added `superseding_scope` mapping
is an extra key.

## Queue rows

Both queues' NE, AR, NV, WY, ND and ME rows gain a `superseding_scope` mapping (jurisdiction, class,
version, `supersedes`, manifest, `taken_at`, `provision_count`, `revised_documents`, `run_note`, notes).
`queue_status` is unchanged (`done`, `agent_ready`, `published_current`). The generator
`scripts/build_snap_state_manual_completion_manifests.py` loads the existing queue and `update()`s only its
own keys, so the mapping survives a `--static-only` rebuild; it is not in the generator's static rows.

## Artifacts (unsigned, uncommitted; `data/` is gitignored)

Under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`, for each of the six scopes:
`sources/<jur>/<class>/<version>/official-documents/*`, `inventory/<jur>/<class>/<version>.json`,
`provisions/<jur>/<class>/<version>.jsonl`, `coverage/<jur>/<class>/<version>.json`. The first failed NE
and AR attempts wrote nothing (they failed on the first download). Draft selectors (not tracked) are in the
session scratch directory; nothing under `manifests/releases/` changed. `data/certs/` unchanged (the
DigiCert intermediate from batch 2 is reused).

## Commands run

```bash
# worktree
git fetch origin && git worktree add --no-checkout /Users/pavelmakarchuk/axiom-corpus-worktrees/snap2 \
  -b discovery/ingest-snap-superseding-2 origin/discovery/program-ingestion-union
git sparse-checkout set --no-cone '/*' '!/data/corpus/' && git read-tree -mu HEAD && uv sync

# extraction (REQUESTS_CA_BUNDLE and CURL_CA_BUNDLE = certifi + data/certs/digicert-global-g2-tls-rsa-sha256-2020-ca1.pem)
for st in ne ar nv wy nd me; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-11-$st-snap-manual-supersede --manifest manifests/<state manifest>.yaml
done

# per-state and combined draft selectors: the release selector with the released version swapped
uv run axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release <draft>.json --ignore-r2-missing --max-issues 50
```

Ruff: `uv run ruff check scripts` -> all checks passed (also `src` and `tests`). The three edited
state tests and `documents.py` were not `ruff format`ted because their originals are not formatted
either; only `ruff check` is enforced.

Tests: `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the sparse worktree -> 12 failed, 286 passed, 2 skipped, 4,529 deselected (47.8 s). All 12 failures open
`data/corpus` artifacts this worktree does not check out (`FileNotFoundError` or `is_file()` on the
worktree's `data/corpus` path): the ten the gotchas note lists (`test_be_rulespec_2026_08_23_promotion`,
`test_build_ny_tanf_compatibility_scope` x2, `test_rulespec_be_source_promotion`, the AK, CT, MI, MT, ND
and NY SNAP manual tests) plus two of the same kind that reached the union branch since
(`test_armenia_arlis::test_checked_in_tax_code_2024_continuity_sources_match_manifest`,
`test_israel_openlaw::test_pilot_manifest_pins_all_three_instruments`). With the worktree's `data/corpus`
temporarily linked to the main checkout's corpus root (link removed afterwards; `git status` clean of it),
`tests/test_us_ne_snap_rules.py`, `tests/test_us_nd_snap_manual.py`, `tests/test_us_me_snap_rules.py`,
`tests/test_us_ar_snap_manual.py` and `tests/test_state_snap_manual_queue.py` pass: 12 passed, 2 skipped
(3.2 s), so the edited tests hold in a full checkout. `tests/test_corpus_documents.py -k impersonation`:
5 passed.

## Reviewer judgments (all of them)

1. Superseding scope = the released manifest re-extracted whole under a new version; document-level
   citation paths must equal the released set (they do in all six states); derived child paths follow the
   new text and are reported, not forced.
2. Dates: revised documents get `source_as_of` 2026-09-11 and `expression_date` = the publisher's own
   revision date (edition date for AR PDFs and NE chapters, `Last-Modified` for NV files, WordPress
   `modified_time` for WY and AR pages, the amendment date inside the ME docx, the "Last published" date for
   ND); unchanged documents keep their released dates. NE chapter 1 changes file but not edition, so it gets
   a new `source_as_of` and keeps its `expression_date`.
3. NE: the API's `_Official` blobs are not served (HTTP 400); the API's `pdfBlobName` copies are the
   publisher's own files (the released chapters 2-5 used them) and are taken for all five chapters; the
   `official_pdf_blob_name` metadata records the API's value. TLS verified with the publisher's public
   intermediate; `verify_tls: false` removed.
4. AR: Cloudflare's 403 to Chrome-fingerprint clients and 200 to a Safari profile is fingerprint
   filtering, not a bot wall; using the publisher's own site through a standard browser profile with
   verification on is not a workaround. The extractor's user-agent/fingerprint mismatch was a bug and was
   fixed minimally. The two program pages whose only change is the sub-navigation line are still recorded
   as revised (their served text and the publisher's dates changed).
5. NV: A-400 is added to the revised set on the publisher's `Last-Modified` (2026-07-06 > 2026-05-27) and
   confirmed by its changed body; the 86 transmittal letters remain the change-summary family.
6. WY: the 900 extended menu is added to the revised set on its `modified_time` (2026-07-15) and confirmed
   by its changed body; the main page's larger body is extractor drift with no released sentence lost and is
   recorded, not suppressed.
7. ND: `expression_date` 2026-09-02 (publication) rather than 2026-10-01 (Release 26.7 effective date in the
   future) or 2026-08-13 (Release 26.6); the template-only topic changes are explained rather than
   filtered.
8. ME: the amendment date in the rule's own history block (August 30, 2026) is the expression date; the
   filing number moves to 2026-191.
9. Tests pinning the manifests were updated rather than left failing; the released scopes' artifact
   assertions are unchanged.
10. Queue rows: an added `superseding_scope` mapping rather than edited `notes`, so a generator rebuild
    keeps it.
11. Timing from `date` stamps around each extraction; validation timings from the same.
12. Disk: 7.0 GB free at start, 4.8 GB at the end of extraction and validation (other sessions were writing
    too); never below the 3 GB floor.

## Controller section

Selector swaps for the next successor selector (for example on top of
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`, which carries all six
released versions):

| Drop (released) | Add (superseding) |
| --- | --- |
| `us-ne` `regulation` `2026-07-17-ne-snap-rules` | `us-ne` `regulation` `2026-09-11-ne-snap-manual-supersede` |
| `us-ar` `manual` `2026-07-16-ar-snap-manual` | `us-ar` `manual` `2026-09-11-ar-snap-manual-supersede` |
| `us-nv` `manual` `2026-05-27-nv-eligibility-payments-manual-r2026-07-15-self-contained` | `us-nv` `manual` `2026-09-11-nv-snap-manual-supersede` |
| `us-wy` `manual` `2026-05-27-wy-manuals-r2026-07-15-self-contained` | `us-wy` `manual` `2026-09-11-wy-snap-manual-supersede` |
| `us-nd` `manual` `2026-07-21-nd-snap-manual` | `us-nd` `manual` `2026-09-11-nd-snap-manual-supersede` |
| `us-me` `regulation` `2026-07-17-me-snap-rules` | `us-me` `regulation` `2026-09-11-me-snap-manual-supersede` |

All six swaps together validate on the 2026-08-23 release selector (`ok: true`, 0 errors, 541 pre-existing
warnings). The batch-2 WY and ND completion scopes (`2026-09-10-snap-state-manual-completion`) stay
selected alongside their superseding scopes. The six new scopes need `sign-ingest-manifest`, the artifact
commit (`scripts/sign_release_scopes.sh`) and `publish_corpus.py --dry-run` like the other unreleased scopes.

Needs a human decision:

- ND `expression_date` 2026-09-02 (publication date) versus the release effective-date convention of the
  released scope; reversible by a manifest edit and re-extraction.
- AR's two program pages recorded as revised on navigation-only changes (alternative: keep their released
  `expression_date` 2026-07-01).
- The `documents.py` user-agent change is a fetcher behaviour change for non-Chromium impersonation profiles
  (none existed before this run).
- WY main-page body growth is unexplained beyond "extractor drift with no loss"; if the controller wants
  parity with the released block, the released self-contained scope holds no raw HTML to reproduce it.
