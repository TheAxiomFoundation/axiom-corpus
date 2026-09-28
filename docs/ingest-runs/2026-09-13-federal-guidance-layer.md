# Federal agency rulebook and guidance layer: POMS SI remainder, POMS HI, CMS IOM Pub 100-16 and 100-18, FNS SNAP and WIC guidance, 2026 annual figures

Date: 2026-09-13
Work order: the federal AGENCY RULEBOOK and guidance gaps of the needs-driven closure check
(`docs/coverage/needs-closure-2026-09-11/{ssi,medicare,snap,wic,liheap}.md`; element ids cited per family).
Branch `discovery/ingest-federal-guidance-layer` cut from `origin/main` (8dc613000) in the sparse worktree
`~/axiom-corpus-worktrees/federal-guidance` (`data/corpus/` excluded, never symlinked); every extraction wrote to the
main checkout's corpus root (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`). Agent timing: started
2026-09-13T15:40-04:00, finished about 16:25-04:00; per-family seconds below.
Impact analysis: not run; the GitNexus MCP tools were unavailable in this session. No library function was modified.
Code changes are confined to three generator scripts: `scripts/build_ssi_poms_si_manifests.py` (families and part HI),
`scripts/build_cms_iom_100_01_manifests.py` (two publications and the heading shapes they print) and the new
`scripts/build_federal_guidance_layer_manifests.py` (the four guidance scopes and their queue records).
Disk: `df -h /` 21 GiB free at start; other sessions' work took it to 5.8 GiB by the end; never below the 3 GiB stop
line (checked before each family; the eight source directories total about 190 MB).

Eight scopes, all jurisdiction `us`:

| Family | Scope | Documents | Provision rows | Extract s | Generator s |
| --- | --- | ---: | ---: | ---: | ---: |
| POMS SI remainder | `us/manual/2026-09-13-ssi-poms-si-remainder` | 778 | 7,046 | 61 | 74 |
| POMS HI | `us/manual/2026-09-13-medicare-poms-hi` | 922 | 4,710 | 80 | 56 |
| IOM Pub 100-16 | `us/manual/2026-09-13-medicare-cms-iom-100-16` | 23 | 1,056 | 11 | 12 |
| IOM Pub 100-18 | `us/manual/2026-09-13-medicare-cms-iom-100-18` | 7 | 440 | 6 | 7 |
| SNAP FNS guidance | `us/guidance/2026-09-13-snap-fns-guidance` | 15 | 64 | 8 | (static) |
| WIC FNS guidance documents | `us/guidance/2026-09-13-wic-fns-guidance-documents` | 6 | 75 | 9 | (static) |
| Medicare annual notices 2026 | `us/guidance/2026-09-13-medicare-annual-notices-2026` | 9 | 330 | 3 | (static) |
| LIHEAP annual figures 2026 | `us/guidance/2026-09-13-liheap-annual-figures-2026` | 6 | 23 | 1 | (static) |

Every scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths, and every document
carries text in at least one row (checked over the JSONL: no document without a non-empty block or page body). No
`ocr: true` was needed except one scanned WIC memorandum (below). `--source-as-of 2026-09-13`; every document's
`expression_date` comes from the document (POMS printed Effective Dates, IOM transmittal lines, memo dates, Federal
Register publication dates, table effective dates); the CLI `--expression-date` fallback was never used.

## Publisher access (2026-09-13)

- `secure.ssa.gov/poms` served the SI and HI chapter lists, subchapter lists and 1,700 section pages to the plain
  corpus client (HTTP 200; `browser_impersonation` stays in the manifests as the fallback only).
- `www.cms.gov` served the IOM index, publication pages, the Prescription Drug Benefit Manual page and all 32 chapter
  PDFs, the fact sheets, memoranda and the enrollment guidance to the plain client.
- `www.fna.usda.gov` (the FNS site since the 2026-06-01 rename; `www.fns.usda.gov` redirects to it) answered HTTP 200
  to the plain client today, unlike the 403 the 2026-09-10 WIC run met, so no origin-host read was needed. Its memo
  pages carry no text of their own: each embeds a PDF from the USDA guidance portal
  (`www.usda.gov/sites/default/files/guidance-documents/`), which answers 403 to plain and browser-UA `curl` alike
  and serves the file to the extractor's `browser_impersonation` (curl_cffi chrome) fetch. The FNA-hosted files (SUA
  table, ABAWD lists, BBCE chart) download directly.
- `www.govinfo.gov` (Federal Register notices), `acf.gov` and `aspe.hhs.gov` served everything to the plain client.
- TLS chains were intact everywhere; nothing in `data/certs/` and no `REQUESTS_CA_BUNDLE` was needed. No mirror,
  archived copy or proxy was used (the two released OBBB memo scopes of August 2026 used web.archive.org copies; the
  new memos come from the publisher's portal).

## Collisions

The follow-up draft `docs/ingest-runs/2026-09-13-us-rulespec-followup-union.selector.json` carries five `us/manual`
scopes (POMS SI 2026-09-10, IOM 100-01, 100-24, 100-02, 100-04) and eighteen `us/guidance` scopes. The
official-documents extractor emits only document rows and their heading/page/sheet sub-rows, no part-, chapter- or
publication-level container rows (checked on the released POMS SI and IOM scopes: no `us/manual/ssa/poms` or
`us/manual/cms/iom/100-02` row exists), so a second POMS scope under new section paths and a new IOM publication
under `us/manual/cms/iom/100-16/...` collide with nothing and no consolidation was needed. The remainder scope's
paths are the section numbers the 2026-09-10 scope did not take (the generator's `exclude` list is the released
`TAKEN_SUBCHAPTERS`); the two scopes together hold every section of part SI. The guidance paths are new
(`us/guidance/usda/fns/snap-...`, `us/guidance/fns/wic/guidance/...`, `us/guidance/cms/.../2026`,
`us/guidance/hhs/aspe/poverty-guidelines/2026...`, `us/guidance/acf/ocs/liheap-im/2026-01...`). The draft selector
`docs/ingest-runs/2026-09-13-federal-guidance-layer.selector.json` (the follow-up draft plus these eight scopes,
564 scopes) validates with `--ignore-r2-missing`: `ok: true`, 0 errors, 546 warnings, all the pre-existing
`missing_parent_id` warnings of `us-ca/regulation/2026-07-13-recovery`.

## Family 1: POMS part SI, the 56 subchapters not taken on 2026-09-10 (SSI)

Closure elements: `SSI-F-POMS-SI-00500`, `-00510`, `-00515`, `-00529`, `-00530`, `-00600` to `-00605`, `-00800`,
`-00832`, `-00870`, `-01100`, `-01150`, `-01200`, `-01210`, `-01220`, `-01300`, `-01700`, `-01715`, `-01730`,
`-01800`, `-01801`, `-02000`, `-02002`, `-02003`, `-02004`, `-02006`, `-02007`, `-02009`, `-02100`, `-02101`,
`-02200`, `-02201`, `-02205`, `-02220`, `-02300`, `-02301`, `-02302`, `-02305`, `-02306`, `-02309`, `-02310`,
`-02900`, `-02901`, `-04000` to `-04070` (the 56 EXTRACTABLE rows of ssi.md's POMS family). `SSI-F-ANN-FBR`,
`-SEIE` and `-SGA` were already PRESENT (`us/guidance/2026-07-05-ssa-cola-2026`,
`2026-05-17-ssa-automatic-determinations-2026`) and were not re-taken.

Source and method exactly as `docs/ingest-runs/2026-09-10-ssi-poms-si.md` (index
`chapterlist!openview&restricttocategory=05`, one document per section, citation path
`us/manual/ssa/poms/si/<section>`, `div.poms` body, transmittal to metadata, printed Effective Dates as
`expression_date`; all 778 sections print one, range 1989-11-30 to 2026-09-11). Generator:
`uv run python scripts/build_ssi_poms_si_manifests.py --family si-remainder --print-index` (manifest
`manifests/us-ssa-poms-si-remainder-2026-09-13.yaml`; the queue's federal row gains a `remainder_scope` record; the
default `si-core` family still reproduces the 2026-09-10 manifest). The index re-read live on 2026-09-13 lists the
same 1,693 sections as on 2026-09-10; 915 are in the released scope, 778 here, none in both.

Counts against the index (sections listed = taken for every subchapter): SI 00500 1, 00510 9, 00515 5, 00529 1,
00530 41; SI 006 (00600-00605) 133; SI 00800 1, 00832 7, 00870 20; SI 01100 1, 01150 37; SI 012 (01200, 01210,
01220) 52; SI 01300 1; SI 017 (01700, 01715, 01730) 45; SI 018 (01800, 01801) 35; SI 02000 1, 02002 6, 02003 45,
02004 8, 02006 15, 02007 5, 02009 16; SI 021 15; SI 022 (02200, 02201, 02205, 02220) 54; SI 023 (02300-02310) 165;
SI 029 6; SI 040 (04000-04070) 53. Total 778 = 1,693 - 915. Regional sections are included (the `.000`
table-of-contents sections too, as in the released scope).

Still missing: nothing in part SI. The state-supplement rows (SSI-ST-*) are outside this order.

## Family 2: POMS part HI, whole part (Medicare)

Closure elements: `MED-F-POMS-HI-00801`, `-00805`, `-00815`, `-01001`, `-01101`, `-03001` (the six EXTRACTABLE
POMS rows of medicare.md). The whole part was taken so that coverage against the publisher's index is meaningful:
11 chapters, 61 subchapters, 922 sections (index `chapterlist!openview&restricttocategory=06`, read live). Citation
path `us/manual/ssa/poms/hi/<section>`; same extraction as part SI; every section prints an Effective Dates line
(range 1989-09-15 to 2026-07-22). Generator `--family hi` (manifest `manifests/us-ssa-poms-hi-2026-09-13.yaml`); the
Medicare queue's federal row gains a `poms_hi` record with the per-chapter inventory.

Counts against the index (listed = taken): HI 002 42 (00200 1, 00201 8, 00204 5, 00208 28); HI 004 33 (00400 1,
00401 32); HI 006 185 (00600 1, 00601 82, 00610 58, 00620 26, 00630 18); HI 008 311 (00800 1, 00801 94, 00803 13,
00805 104, 00810 2, 00815 31, 00820 24, 00825 27, 00830 15); HI 009 36 (00900 1, 00901 20, 00920 3, 00930 12);
HI 010 119 (01000 1, 01001 86, 01005 21, 01015 11); HI 011 87 (01100 1, 01101 10, 01120 16, 01130 8, 01140 9,
01190 20, 01194 23); HI 012 3; HI 022 6; HI 030 97 (03000 1, 03001 5, 03010 10, 03020 13, 03030 7, 03035 10,
03040 6, 03050 6, 03090 2, 03092 4, 03094 33); HI 041 3. Total 922.

Still missing: nothing in part HI.

## Family 3: CMS IOM Pub 100-16 (Medicare Managed Care Manual) and Pub 100-18 (Prescription Drug Benefit Manual)

Closure elements: `MED-F-IOM-100-16`, `MED-F-IOM-100-18` (medicare.md). Pub 100-03 and 100-05 (`MED-F-IOM-100-03`,
`-100-05`) were not in this order and were not taken.

Both publications were added to `scripts/build_cms_iom_100_01_manifests.py` as `Publication` records with the
adaptive heading pattern of the 100-02/100-04 run (`docs/ingest-runs/2026-09-11-medicare-cms-iom-100-02-100-04.md`)
and proven the same way: every chapter PDF's TOC was parsed, a scratch-base extraction was compared with the TOC
labels chapter by chapter, and the shapes the two manuals print that the earlier publications did not were added to
the generator (they do not change the checked-in 100-01/100-02/100-04/100-24 manifests, which were left untouched):

- lettered chapters (`Chapter 16a - Subchapter A - ...`): the chapter key keeps the letter (`chapter-16a`);
- Pub 100-18's IOM publication page (cms050485) links only the two-page table of contents `pub100_18.pdf`; the chapter
  PDFs are on the publisher's Prescription Drug Benefit Manual page
  (`/medicare/coverage/prescription-drug-coverage-contracting/prescription-drug-benefit-manual`), recorded as
  `Publication.chapter_page` and in each document's metadata; two of them have no `.pdf` extension (`chapter7pdf`,
  `r6pdbpdfpdf`), so a chapter-labelled link under `/downloads/` is a chapter when its bytes are a PDF;
- transmittal forms "(Rev. 73, 09 30 05)" (spaces, 100-16 ch. 15), "Last Updated - Rev. 52, 05-07-04" (no
  parentheses, ch. 17a/17c), "(Chapter 9 - Rev. 16, 01-11-13)" / "(Chapter 21 - Rev. 110, 01-11-13)" (the joint
  compliance chapter, one PDF posted as 100-16 ch. 21 and 100-18 ch. 9; only the line naming the chapter being built
  counts) and chapters with no transmittal in the TOC header at all (100-16 ch. 18a, 18c: the latest section
  transmittal dates the chapter, recorded in `expression_date_source`);
- chapters that print no "Transmittals for Chapter" line (100-16 ch. 17a, 17c, 17d, 17f, 18a, 18c; 100-18 ch. 12, a
  CMS Manual System transmittal wrapping the chapter): the "Table of Contents" line ends the header instead
  (`metadata.toc_header_rule`);
- 100-16 ch. 16a's last TOC line is the wrapped fragment "Network PFFS Plan" shared by three TOC entries; the anchor
  walks back to the nearest unique TOC line (`metadata.toc_anchor_note`);
- bold regulatory citations under headings ("42 CFR §422.158(e)", "42 C.F.R. §§ 422.503(b)(4)(vi)(G), ...") matched
  the heading pattern as section "42" in five chapters (100-16 ch. 5, 10, 16a, 21; 100-18 ch. 9) and produced
  duplicate paths in the scratch run; a heading never starts with "CFR"/"C.F.R.", so the pattern now excludes them;
- "(Chapter 21, Rev. 110, ...)" transmittal lines were absorbed into headings by the continuation pattern; excluded
  like "(Rev. ...)";
- 100-18 ch. 13 prints section 30.2 as "30.1- Partial Subsidy Eligible Individuals" (the preceding label repeated);
  `text_replacements` override, as the 100-02 ch. 7/11 fixes.

Pub 100-16 (publication page cms019326, `manifests/us-cms-iom-100-16.yaml`, 25 chapter links): 23 chapters taken;
chapters 3 (marketing) and 13 (grievances and appeals) are one-page pointers to standalone cms.gov guidance and are
recorded as not taken (`pointer_chapters`); chapters 2, 17e, 19 and 20 are not posted. Per chapter: TOC sections /
emitted sections / empty bodies, expression date: 1 15/15/0 2017-02-10; 4 151/150/0 2016-04-22 (10.8 printed
non-bold in the body, text stays in 10.7.4); 5 37/37/0 2014-08-08; 6 18/18/1 2007-04-27 (80 is a container followed
by 80.1); 7 49/49/0 2014-09-19; 8 49/49/0 2014-09-19; 9 48/48/0 2013-05-03; 10 10/10/0 2011-11-04; 11 45/45/0
2007-04-25; 12 15/15/0 2013-05-17; 14 20/20/0 2016-05-27; 15 6/6/0 2005-09-30; 16a 70/70/0 2011-05-27; 16b 87/88/1
2024-11-22 (the TOC misprints 20.2.1.1.1-20.2.1.1.5 for the body's 20.2.1.2.1-20.2.1.2.5 and omits 20.2.10.1; the
body governs; "10 Introduction" is a container); 17a 46/46/0 2004-05-07; 17b 80/80/0 2007-04-27; 17c 15/15/0
2003-01-01; 17d 53/53/0 2003-10-31; 17f 61/60/0 2005-10-28 (120 printed non-bold, text stays in 110); 18a 37/37/0
2005-08-12; 18b 66/66/0 2007-04-27; 18c 11/11/0 2003-09-05; 21 45/45/0 2013-01-11. Total 1,034 TOC labels,
1,033 sections, 2 empty containers; 1,056 rows = 23 chapter roots + 1,033 sections.

Pub 100-18 (`manifests/us-cms-iom-100-18.yaml`, 7 chapter PDFs on the PDBM page): 5 85/85/0 2011-09-30 (opens with
a transmittal cover letter); 6 78/78/0 2016-01-15; 7 42/42/0 2010-02-19; 9 45/45/0 2013-01-11 (joint chapter; its
sections carry no transmittal lines); 12 55/55/0 2008-11-07; 13 66/66/0 2018-10-01; 14 63/62/0 2018-09-17 (50.15.1
printed non-bold, text stays in 50.15). Total 434 TOC labels, 433 sections, 0 empty; 440 rows.

Still missing: Pub 100-18 chapters 1, 8, 16, 17 (reserved), 10, 11, 15 (never disseminated via Pub 100-18 per its
table of contents), chapter 2 (published as the Medicare Communications and Marketing Guidelines), chapter 4
(published as the creditable-coverage guidance pages) and chapter 18 (the Parts C & D Enrollee Grievances,
Organization/Coverage Determinations, and Appeals Guidance, linked on the PDBM page); the two Pub 100-16 pointer
chapters' standalone documents. Chapter 3 (eligibility and enrollment) no longer exists as a chapter; its successor,
the CY 2026 Medicare Advantage and Part D Enrollment and Disenrollment Guidance, is taken in family 6. The Medicare
queue's `index_families` marks 100-16 and 100-18 `taken` and lists the not-taken documents per publication.

## Family 4: FNS SNAP guidance from www.fna.usda.gov (snap.md)

Closure elements: `snap_g09` (full FY 2026 COLA memorandum: minimum benefit $24 for the 48 states and D.C.),
`snap_g10` (state SUA table), `snap_g11` (ABAWD waiver status lists), `snap_g12` (BBCE chart), `snap_g15` (the other
OBBB implementation memoranda); `snap_g14` gains the alien-eligibility Q&A #1. `snap_g13` and `snap_g14`'s
memoranda were already released and are not re-taken. `snap_g16` (State Options Report) stays out under the queues'
forbidden-sources policy.

Scope `us/guidance/2026-09-13-snap-fns-guidance`, 15 documents, citation paths `us/guidance/usda/fns/<slug>` (the
convention of the released SNAP guidance scopes), generator `scripts/build_federal_guidance_layer_manifests.py --only
snap` (manifest `manifests/us-snap-fns-guidance-2026-09-13.yaml`; the SNAP completion queue gains a federal row with a
`federal_guidance_scope` record):

- `snap-fy2026-cola-memo`: the seven-page FY 2026 COLA memorandum (portal PDF behind `/snap/allotment/cola/fy26`;
  effective 2025-10-01, the convention of the released tables scope; the memo prints no date line);
- `snap-fy2026-standard-utility-allowances`: the FNA SUA page's "FY 2026 SUAs - Updated August 2026" workbook
  (`2026-05-21-SUA-Table-FY26.xlsx`, one sheet, 104 rows: HCSUA, BUA/LUA, single-utility, phone and SMD offset by
  state; effective 2025-10-01 to 2026-09-30), extracted as one sheet row;
- `snap-abawd-waiver-status-fy2026-q1`, `-q2`, `-q3`: the FY 2026 quarterly status lists from `/snap/waivers/timelimit`
  (dated 2025-10-01, 2026-01-01, 2026-03-01); the page lists no FY 2026 Q4 list yet;
- `snap-bbce-state-chart-2026-06`: the June 2026 BBCE states chart (4 pages);
- nine OBBB memoranda and Q&As listed on `/obbb`: the information memorandum (2025-09-04), ABAWD waivers
  implementation memorandum (2025-10-03), QC variance exclusion Q&As (2025-11-14), time-limit changes Q&As #1
  (2026-06-11), FY 2026 SUA simplified process (2025-08-15), treatment of energy assistance payments (2025-08-29),
  internet expenses and energy assistance Q&As #1 (2026-05-08), section 10106 administrative cost sharing Q&As
  (2026-05-21), alien eligibility Q&As #1 (2025-12-09). Memo dates read from the PDFs.

Still missing: the FY 2026 Q4 ABAWD list (not posted); the two SNAP-Ed OBBB Q&As on the same index (nutrition-education
grant administration, not household rules; not taken); the State Options Report (forbidden source).

## Family 5: FNS WIC guidance documents (wic.md)

Closure elements: `wic_g04` (nutrition risk criteria list: WIC Policy Memorandum #2011-5, the list of allowed
nutrition risk criteria, 8 pages), `wic_g07` (infant formula rebate and cost-containment guidance: the 2019
informational memorandum on bidding for single milk- and soy-based formula, WPM #1999-3 evaluation criteria for rebate
contracts, the June 2006 Interim Guidance on WIC Vendor Cost Containment (46 pages) and WPM #2006-6), `wic_g08`
(state plan guidance: WPM #2024-3 Implementing ABFA Requirements in WIC State Plans). All six are in the FNA resource
browser's WIC Guidance Documents family (195 documents by its own facet count; the browser's pagination works from
the front door today, unlike the origin-host read of 2026-09-10) and each page embeds its PDF from the USDA guidance
portal. Scope `us/guidance/2026-09-13-wic-fns-guidance-documents`, paths `us/guidance/fns/wic/guidance/<slug>`,
manifest `manifests/us-wic-fns-guidance-documents-2026-09-13.yaml`; the WIC queue's federal row gains a
`guidance_documents_scope` record. WPM #1999-3 is a scan whose embedded text layer is garbled (its header reads
"GCl \4 1918"); it is re-read with `ocr: true` + `force_ocr: true` at 300 dpi (tesseract on PATH) and its three pages
carry 6,826 characters; its date is the index listing's 1998-10-14.

Still missing (lower priority per the order, not reached): the 143 pre-FY 2025 policy memoranda (`wic_g05`) and the
70 Federal Register notices (`wic_g06`) of the same browser. FNS publishes no standalone WIC state plan template on
the browser (the template lives in the WiSP state-agency portal; the 2025-09-25 WiSP information-collection notice
is a Federal Register notice of the `wic_g06` family), so `wic_g08` is closed by the ABFA state-plan memorandum only.

## Family 6: Medicare annual figures for 2026 (medicare.md)

Closure elements: `MED-F-ANN-AB` (the three CY 2026 Federal Register notices of 2025-11-19, govinfo HTML: Part A
premiums 90 FR 52060, inpatient deductible and coinsurance 90 FR 52075, Part B actuarial rates, premium and deductible
90 FR 52063; and the CMS fact sheet "2026 Medicare Parts A & B Premiums and Deductibles" of 2025-11-14, which carries
the IRMAA brackets), `MED-F-ANN-D` (the CMS fact sheet "2026 Medicare Part D Bid Information and Part D Premium
Stabilization Demonstration Parameters" and the national average bid amount memorandum, both 2025-07-28, base
beneficiary premium $38.99; the CY 2026 Rate Announcement of 2025-04-07, 151 pages, whose Attachment V carries the
defined standard benefit parameters), `MED-F-ANN-LIS` (the CY 2026 LIS resource and cost-sharing limits memorandum of
2025-10-31), plus the CY 2026 Medicare Advantage and Part D Enrollment and Disenrollment Guidance (145 pages, updated
2025-08-01), the successor of Pub 100-18 chapter 3 (`MED-F-IOM-100-18`). `MED-F-ANN-POVERTY` is closed by family 7.
Scope `us/guidance/2026-09-13-medicare-annual-notices-2026`, paths `us/guidance/cms/<figure>/2026[/federal-register|
/fact-sheet]`, manifest `manifests/us-cms-annual-notices-2026.yaml`; the Medicare queue's federal row gains an
`annual_notices_2026` record. The `cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-and-deductibles`
slug the closure report guessed answers 404; the published slug omits "and".

Still missing: nothing the report named for 2026; earlier years are not taken.

## Family 7: LIHEAP annual figures for FY 2026 (liheap.md)

Closure elements: `LIHEAP-F-ANN-POVERTY` and `MED-F-ANN-POVERTY` (the 2026 HHS poverty guidelines notice, 91 FR 1797,
2026-01-15, govinfo HTML, and the ASPE poverty guidelines page carrying the 2026 tables), `LIHEAP-F-ANN-SMI` (ACF
LIHEAP IM 2026-01 of 2026-04-24: the page, the memorandum PDF, Attachment 4 "State Median Income by Household Size for
Mandatory Use in FY27" (optional in FY 2026) and Attachment 2, the 100/110/150 percent FPG tables). The IM index
`acf.gov/ocs/policy-guidance/liheap-information-memoranda` lists IM 2026-01 as the current FPG/SMI memorandum. Scope
`us/guidance/2026-09-13-liheap-annual-figures-2026`, paths `us/guidance/hhs/aspe/poverty-guidelines/2026[/federal-register]`
and `us/guidance/acf/ocs/liheap-im/2026-01[/memorandum|/attachment-4-smi-table|/attachment-2-fpg-tables]`, manifest
`manifests/us-liheap-annual-figures-2026.yaml`; the LIHEAP queue's federal row gains an `annual_figures_scope` record
(its `needs_review` status for the statute and regulation leads is unchanged). The undated path
`us/guidance/hhs/aspe/poverty-guidelines` of `manifests/us-hhs-poverty-guidelines.yaml` was never extracted (no
provisions JSONL carries it) and is left as is.

Still missing: `LIHEAP-F-GUID-MODELPLAN` (the model plan form and instructions, action transmittals) and the LIHEAP
statute and 45 CFR 96 subpart H, which other agents' U.S. Code and eCFR runs cover.

## Tests

`uv run ruff check scripts`: passes. `uv run pytest -q -m "not integration and not slow" -k "manifest or
official_documents or discovery"` in the sparse worktree: 286 passed, 2 skipped, 12 failed, all `FileNotFoundError`
(one surfacing as an assertion) on other scopes' `data/corpus` artifacts the sparse checkout does not contain:
`test_armenia_arlis`, `test_be_rulespec_2026_08_23_promotion`, `test_build_ny_tanf_compatibility_scope` (x2),
`test_israel_openlaw`, `test_rulespec_be_source_promotion`, and the AK, CT, MI, MT, ND, NY SNAP manual tests. None
touches the three generator scripts or the new manifests (the vault gotchas note records the same failure set for
every sparse worktree). No adapter was added, so no new tests.

## Controller

Selector additions (all jurisdiction `us`; artifacts unsigned, on the controller's disk under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus`, not committed):

| document_class | version |
| --- | --- |
| manual | 2026-09-13-ssi-poms-si-remainder |
| manual | 2026-09-13-medicare-poms-hi |
| manual | 2026-09-13-medicare-cms-iom-100-16 |
| manual | 2026-09-13-medicare-cms-iom-100-18 |
| guidance | 2026-09-13-snap-fns-guidance |
| guidance | 2026-09-13-wic-fns-guidance-documents |
| guidance | 2026-09-13-medicare-annual-notices-2026 |
| guidance | 2026-09-13-liheap-annual-figures-2026 |

`docs/ingest-runs/2026-09-13-federal-guidance-layer.selector.json` is the follow-up draft plus these eight (564
scopes); `validate-release --ignore-r2-missing` on it: `ok: true`, 0 errors, 546 warnings (pre-existing). No
released scope is swapped or superseded. Remaining steps are the controller's: `sign-ingest-manifest` for the eight
scopes, merge with the other 2026-09-13 branches' additions (U.S. Code, eCFR parts, state plans) into one selector,
re-validate, sign, publish, activate.

Rebuild:

```bash
uv run python scripts/build_ssi_poms_si_manifests.py --family si-remainder --print-index
uv run python scripts/build_ssi_poms_si_manifests.py --family hi --print-index
uv run python scripts/build_cms_iom_100_01_manifests.py --publication 100-16
uv run python scripts/build_cms_iom_100_01_manifests.py --publication 100-18
uv run python scripts/build_federal_guidance_layer_manifests.py
for scope in \
  "manual 2026-09-13-ssi-poms-si-remainder us-ssa-poms-si-remainder-2026-09-13" \
  "manual 2026-09-13-medicare-poms-hi us-ssa-poms-hi-2026-09-13" \
  "manual 2026-09-13-medicare-cms-iom-100-16 us-cms-iom-100-16" \
  "manual 2026-09-13-medicare-cms-iom-100-18 us-cms-iom-100-18" \
  "guidance 2026-09-13-snap-fns-guidance us-snap-fns-guidance-2026-09-13" \
  "guidance 2026-09-13-wic-fns-guidance-documents us-wic-fns-guidance-documents-2026-09-13" \
  "guidance 2026-09-13-medicare-annual-notices-2026 us-cms-annual-notices-2026" \
  "guidance 2026-09-13-liheap-annual-figures-2026 us-liheap-annual-figures-2026"; do
  set -- $scope
  s=$(date +%s); uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version "$2" \
    --manifest "manifests/$3.yaml" --source-as-of 2026-09-13 --expression-date 2026-09-13
  echo "elapsed_seconds=$(( $(date +%s) - s )) scope=us/$1/$2"
done
uv run axiom-corpus-ingest validate-release --base data/corpus \
  --release docs/ingest-runs/2026-09-13-federal-guidance-layer.selector.json --ignore-r2-missing --max-issues 50
```
