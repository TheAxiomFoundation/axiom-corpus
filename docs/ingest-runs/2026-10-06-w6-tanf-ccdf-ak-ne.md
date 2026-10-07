# Wave 6, group tanf-ccdf-ak-ne: state TANF and CCDF bundle documents, Alaska to Nebraska

Date: 2026-10-06 (evening, US Eastern).
Work order: `docs/coverage/program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-ak-ne.csv` (372 rows, 371 Tier 1, 30
jurisdictions, every row `pe_cited_units` 1 except NC 108A-27.01) with `wave6/00-common-preamble.md` and
`wave6/tanf-ccdf-ak-ne-brief.md` (branch `analysis/program-bundle-gaps-2026-10-06`).
Worktree `~/axiom-corpus-worktrees/w6-tanf-ccdf-ak-ne` (sparse, `data/corpus/` excluded, never symlinked), branch
`discovery/ingest-w6-tanf-ccdf-ak-ne` cut from main e16ccb799. Every extraction wrote to the main checkout's corpus root
(`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`); nothing under `data/corpus/` is committed, nothing was signed,
locked, pushed to R2 or loaded to Supabase. Working files in the scratchpad folder `w6-tanf-ccdf-ak-ne` (the shared `w6`
folder was overwritten by another agent early on; the probe was re-run in the group folder).

Outputs: this note; `docs/ingest-runs/2026-10-06-w6-tanf-ccdf-ak-ne-decisions.csv` (372 rows, one per work-order row);
67 manifests `manifests/us-xx-tanf-ccdf-w6-{docs,manual,rules,statutes,forms,ccap-manual}.yaml`; the generator
`scripts/build_w6_tanf_ccdf_ak_ne_manifests.py`; one intermediate certificate
`data/certs/globalsign-rsa-ov-ssl-ca-2018.pem`; one `program_bundle_documents_2026_10_06` family per jurisdiction on
`manifests/tanf-agent-queue.yaml` (28 rows) and `manifests/ccdf-agent-queue.yaml` (25 rows).

## Decisions

| action | PRESENT | ALREADY-HELD | OUTREACH | ABSENT | OUT-OF-SCOPE | SKIPPED | total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| EXTRACT-MANIFEST | 2 | 1 | 0 | 0 | 0 | 0 | 3 |
| FETCH | 219 | 12 | 0 | 0 | 4 | 0 | 235 |
| CHECK-PUBLISHER | 16 | 1 | 1 | 2 | 2 | 0 | 22 |
| OFFICIAL-SOURCE | 46 | 12 | 4 | 0 | 0 | 0 | 62 |
| DEAD-LINK | 8 | 3 | 0 | 4 | 0 | 0 | 15 |
| BLOCKED-CHECK | 22 | 2 | 8 | 1 | 0 | 0 | 33 |
| PATH-ONLY | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| all | 314 | 32 | 13 | 7 | 6 | 0 | 372 |

By program: TANF 196 rows (157 PRESENT, 25 ALREADY-HELD, 8 OUTREACH, 3 ABSENT, 3 OUT-OF-SCOPE), CCDF 176 rows (157
PRESENT, 7 ALREADY-HELD, 5 OUTREACH, 4 ABSENT, 3 OUT-OF-SCOPE). Every PRESENT and ALREADY-HELD citation path was looked
up in the named scope's provisions file by the generator (`0 path problems`); the one exception is row 63, held by a
released scope that exists only as a lock file (below). Where the official address differs from `bundle_url` the
decision's `official_url` names the address fetched, so `scripts/apply_wave_decisions.py` joins the bundle address to
the path.

## Method

1. **Held already?** For each row: the bundle address (normalized: host without `www.`, decoded path, query kept
   minus cache-busters) against every `source_url`/`download_url` of the local inventories of the 30 jurisdictions;
   the last URL segment as a token against the same inventories; section numbers against the statute and regulation
   provisions; and, after the controller's correction, the SHA-256 of every source file this run took against every
   source file of every lock file under `.axiom/corpus-locks/` for these jurisdictions (29,723 locked source hashes;
   18 locked scopes have no bytes in the local root) and against all other local inventories. 32 rows are held
   (table below). The hash check found no locked duplicate of a document taken here; it found two same-file
   duplicates with other wave-6 groups (AZ ARS 46-207/-207.01/-292 and MO 13 CSR 40-2, below).
2. **Probe.** `build_w6_tanf_ccdf_ak_ne_manifests.py probe`: one plain GET per address with the corpus user agent,
   one thread per host, requests serial within a host with 0.5 s spacing (273 addresses on 90 hosts in 25 s), TLS
   verified against certifi plus the committed `data/certs/*.pem` intermediates. The probe records status, type,
   size, Last-Modified and the first page of text, which the generator reads for titles and dates.
3. **Manifests.** One manifest per jurisdiction and document class, `version: 2026-10-06-w6-<family>-<state>` with
   family `tanf-ccdf-docs` (policy), `tanf-ccdf-manual` (manual), `tanf-ccdf-rules` (regulation),
   `tanf-ccdf-statutes` (statute), `tanf-ccdf-forms` (form), and `ccap-manual` (ND manual 400-28). `source_url` is the
   bundle address wherever that is the address fetched; `download_url` where the document sits behind it (CT eRegs
   section PDFs, FL rule .doc, IN IAR API). Titles are read from the document (page title, PDF title or first line;
   `TITLE_BY_PATH` where those are a file name or a letterhead); `expression_date` is a printed effective or issue
   date on the first page, else the HTTP Last-Modified date, else the source date, recorded as
   `metadata.expression_date_basis`. PDFs are page-level by default, labeled sections where the publisher's
   numbering is stable (MO CSR, NDAC, 10A NCAC 10, IN IAR); HTML heading blocks with a content selector where the
   page needs one (FL DCF, KY LRC version page, ND MadCap topics); Tesseract OCR for six image-only PDFs (AL fact
   sheet, HI fee scale and HAR 17-798.2/798.3, MD AT 19-04 and 20-06).
4. **Adapters.** `extract-illinois-admin-code` (89 IAC 50 and 112; 23 IAC 2060), `extract-montana-admin-rules`
   (ARM 37.78, 37.80), `extract-california-codes --only-title WIC` (the Legislative Counsel bulk file), the
   `ks-kar` builder (K.A.R. article 30-4 from rules.ks.gov, the tax run's method) and the `nd-ccap` builder (the whole
   CCAP Policy Manual 400-28 from its MadCap master TOC).
5. **Extraction.** `extract-official-documents --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --version <v>
   --manifest <m> --source-as-of 2026-10-06`, one manifest at a time, with `REQUESTS_CA_BUNDLE` = certifi + the
   committed intermediates. Every scope: coverage `complete: true`, 0 missing, 0 duplicate citation paths, no
   symlinked or stale source file (the CA bulk extractor stored the zip as a symlink to the download cache; it was
   replaced by the file itself, same SHA-256 2b443092...). `scripts/validate_citation_paths.py` over the 72 scopes:
   `RESULT: OK` (after the CA form path fix below).

## Publisher access (2026-10-06, plain corpus client unless stated)

- Answered the plain client (content, HTTP 200) for at least one address: 84 of the 90 hosts probed, including every agency host of the FETCH
  rows except those listed here, the legislatures' statute pages (azleg.gov, ksrevisor.gov, revisor.mo.gov,
  nebraskalegislature.gov, revisor.mn.gov, ncleg.gov, mgaleg.maryland.gov, legislature.maine.gov), the registers and
  codes (rules.sos.ga.gov, apps.legislature.ky.gov, legis.iowa.gov, sos.mo.gov, ndlegis.gov, regs.maryland.gov,
  doa.la.gov, flrules.org, reports.oah.state.nc.us, ftp.ilga.gov, rules.ks.gov API, rules.mt.gov API,
  leg.state.fl.us), and downloads.leginfo.legislature.ca.gov (1,288,351,194-byte `pubinfo_2025.zip` of 2026-10-05,
  1,068 s at about 1.2 MB/s).
- TLS: `cga.ct.gov` omits its Go Daddy G2 intermediate (the 2026-10-06 check's URLError; answers with the committed
  `godaddy-secure-certificate-authority-g2.pem`); `billstatus.ls.state.ms.us` serves only its leaf (issuer GlobalSign
  RSA OV SSL CA 2018): the public intermediate was fetched from the leaf's AIA URL
  (`http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt`, SHA-256 fingerprint B6:76:FF:A3...:4A, valid to
  2028-11-21) and committed as `data/certs/globalsign-rsa-ov-ssl-ca-2018.pem`. Verification was never disabled.
- Documented browser impersonation used: `www.mass.gov` (EEC policy files and 606 CMR; 403 to the plain client; the
  CCDF and TANF plan runs' `browser_impersonation: true`) and `www.michigan.gov` (TANF plans; same precedent);
  `drxya2s1hkmtl.cloudfront.net` (Indiana IAR API, the tax regulation run's `browser_impersonation_direct`).
  Nothing else was impersonated.
- Script-rendered publishers read through their own data: `eregulations.ct.gov` Browse pages embed the section JSON
  that names the section PDF (`getDocument?guid=SectionPdfGUID`); `rules.sos.ga.gov` rule pages are Fastcase
  script shells, the Subject 290-2-28 page prints every rule; `www.nd.gov/dhs/policymanuals/40028/40028.htm` is a
  MadCap shell (`Data/HelpSystem.xml` names `Data/Tocs/Master.js`); `iar.iga.in.gov` (API above);
  `www.myflfamilies.com` keeps its body outside `<main>`.
- Blocked, not worked around (OUTREACH): `leginfo.legislature.ca.gov` (HTTP 403 to the corpus client and to the
  California section extractor's own user agent; codes taken from the bulk file instead, the four bill pages stay
  blocked); `des.az.gov` and `dbmefaapolicy.azdes.gov` (Cloudflare, documented 2026-09-13/14/15, the 2026-10-06 check
  403 again); `earlychildhood.marylandpublicschools.org` (403 Cloudflare "Just a moment" on the rates page; two filedepot
  files 404); `sos-rules-reg.ark.org` (AWS WAF "Human Verification" CAPTCHA, HTTP 405); `govt.westlaw.com` (403 to the
  corpus client with the tax run's cookies, so 5 CCR 18078 could not be located); `www.ilga.gov` (403 "Access Denied";
  JCAR's `ftp.ilga.gov` serves the same code); `capitol.hawaii.gov` (403 in the check; the section is held).
  Mississippi Code: published only through LexisNexis.
- Not found: `dese.mo.gov` child-care-manual section pages 2010/005/00 and 2025/010 (HTTP 403 Drupal "nothing here",
  the manual is now one PDF), `cde.ca.gov` MB 25-05 (rescinded), `hawaii.edu` Bridge to Hope desk aid, the 2014 LA
  TANF renewal (dcfs.louisiana.gov and dcfs.la.gov), `mass.gov` interim CCFA policies of October 2023 (404 to the
  impersonated client too), `epolicy.dpss.lacounty.gov` (does not resolve), the doa.la.gov `67.pdf` and `28v165.pdf`
  addresses (the OSR now posts `.docx`).

## Scopes (72; 18,235 rows; 43.4 million characters; 1,467 MB of sources, 1,288 MB of it the CA bulk zip)

| Jurisdiction | Class | Version | Docs | Rows | Chars | Source MB | Extract s |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| us-ak | manual | `2026-10-06-w6-tanf-ccdf-manual-ak` | 1 | 707 | 1,441,817 | 5.2 | 6 |
| us-ak | policy | `2026-10-06-w6-tanf-ccdf-docs-ak` | 4 | 29 | 36,606 | 1.1 | 4 |
| us-al | policy | `2026-10-06-w6-tanf-ccdf-docs-al` | 4 | 38 | 90,755 | 1.1 | 5 |
| us-ar | policy | `2026-10-06-w6-tanf-ccdf-docs-ar` | 1 | 5 | 3,106 | 0.4 | 3 |
| us-az | statute | `2026-10-06-w6-tanf-ccdf-statutes-az` | 3 | 6 | 18,696 | 0.0 | 3 |
| us-ca | form | `2026-10-06-w6-tanf-ccdf-forms-ca` | 1 | 2 | 1,664 | 0.0 | 3 |
| us-ca | manual | `2026-10-06-w6-tanf-ccdf-manual-ca` | 7 | 92 | 97,975 | 1.9 | 5 |
| us-ca | policy | `2026-10-06-w6-tanf-ccdf-docs-ca` | 23 | 130 | 184,068 | 6.2 | 13 |
| us-ca | regulation | `2026-10-06-w6-tanf-ccdf-rules-ca` | 4 | 240 | 371,804 | 1.4 | 7 |
| us-ca | statute | `2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-WIC` | - | 7,987 | 14,783,630 | 1288.4 | 8 |
| us-ct | policy | `2026-10-06-w6-tanf-ccdf-docs-ct` | 11 | 215 | 351,205 | 3.4 | 4 |
| us-ct | regulation | `2026-10-06-w6-tanf-ccdf-rules-ct` | 3 | 18 | 42,415 | 0.2 | 3 |
| us-dc | policy | `2026-10-06-w6-tanf-ccdf-docs-dc` | 5 | 235 | 483,675 | 2.7 | 4 |
| us-de | policy | `2026-10-06-w6-tanf-ccdf-docs-de` | 3 | 83 | 135,513 | 1.9 | 5 |
| us-fl | policy | `2026-10-06-w6-tanf-ccdf-docs-fl` | 1 | 7 | 5,382 | 0.0 | 3 |
| us-fl | regulation | `2026-10-06-w6-tanf-ccdf-rules-fl` | 1 | 2 | 6,145 | 0.0 | 3 |
| us-fl | statute | `2026-10-06-w6-tanf-ccdf-statutes-fl` | 1 | 2 | 287,011 | 0.5 | 3 |
| us-ga | manual | `2026-10-06-w6-tanf-ccdf-manual-ga` | 2 | 506 | 1,124,063 | 10.2 | 5 |
| us-ga | regulation | `2026-10-06-w6-tanf-ccdf-rules-ga` | 1 | 20 | 28,329 | 0.1 | 2 |
| us-hi | policy | `2026-10-06-w6-tanf-ccdf-docs-hi` | 3 | 46 | 91,540 | 0.9 | 5 |
| us-hi | regulation | `2026-10-06-w6-tanf-ccdf-rules-hi` | 2 | 127 | 198,996 | 3.5 | 116 |
| us-ia | policy | `2026-10-06-w6-tanf-ccdf-docs-ia` | 4 | 172 | 355,825 | 2.6 | 5 |
| us-ia | regulation | `2026-10-06-w6-tanf-ccdf-rules-ia` | 2 | 65 | 255,661 | 0.8 | 3 |
| us-id | policy | `2026-10-06-w6-tanf-ccdf-docs-id` | 1 | 4 | 1,373 | 0.2 | 3 |
| us-il | policy | `2026-10-06-w6-tanf-ccdf-docs-il` | 4 | 23 | 39,908 | 1.4 | 4 |
| us-il | regulation | `2026-10-06-w6-tanf-ccdf-rules-il-title-023-part-02060` | - | 86 | 160,745 | 0.9 | 19 |
| us-il | regulation | `2026-10-06-w6-tanf-ccdf-rules-il-title-089-part-00050-00112` | - | 135 | 232,933 | 1.2 | 31 |
| us-in | manual | `2026-10-06-w6-tanf-ccdf-manual-in` | 4 | 139 | 310,328 | 4.9 | 6 |
| us-in | policy | `2026-10-06-w6-tanf-ccdf-docs-in` | 9 | 46 | 93,116 | 3.3 | 6 |
| us-in | regulation | `2026-10-06-w6-tanf-ccdf-rules-in` | 1 | 47 | 59,980 | 0.2 | 3 |
| us-ks | manual | `2026-10-06-w6-tanf-ccdf-manual-ks` | 6 | 19 | 43,940 | 0.6 | 5 |
| us-ks | regulation | `2026-10-06-w6-tanf-ccdf-rules-ks` | 79 | 158 | 119,101 | 0.3 | 20 |
| us-ks | statute | `2026-10-06-w6-tanf-ccdf-statutes-ks` | 1 | 2 | 68,079 | 0.1 | 3 |
| us-ky | policy | `2026-10-06-w6-tanf-ccdf-docs-ky` | 3 | 11 | 17,978 | 0.5 | 3 |
| us-ky | regulation | `2026-10-06-w6-tanf-ccdf-rules-ky` | 6 | 370 | 2,277,210 | 4.8 | 7 |
| us-la | policy | `2026-10-06-w6-tanf-ccdf-docs-la` | 5 | 102 | 196,730 | 5.9 | 4 |
| us-la | regulation | `2026-10-06-w6-tanf-ccdf-rules-la` | 5 | 490 | 4,969,714 | 10.9 | 6 |
| us-ma | policy | `2026-10-06-w6-tanf-ccdf-docs-ma` | 8 | 27 | 4,660,404 | 8.6 | 6 |
| us-ma | regulation | `2026-10-06-w6-tanf-ccdf-rules-ma` | 2 | 4 | 767,421 | 1.0 | 3 |
| us-md | policy | `2026-10-06-w6-tanf-ccdf-docs-md` | 4 | 62 | 50,242 | 3.3 | 10 |
| us-md | regulation | `2026-10-06-w6-tanf-ccdf-rules-md` | 4 | 8 | 52,099 | 0.2 | 4 |
| us-md | statute | `2026-10-06-w6-tanf-ccdf-statutes-md` | 2 | 111 | 198,766 | 1.2 | 3 |
| us-me | policy | `2026-10-06-w6-tanf-ccdf-docs-me` | 4 | 22 | 21,525 | 0.5 | 3 |
| us-me | statute | `2026-10-06-w6-tanf-ccdf-statutes-me` | 1 | 3 | 4,428 | 0.1 | 3 |
| us-mi | manual | `2026-10-06-w6-tanf-ccdf-manual-mi` | 2 | 11 | 10,126 | 0.4 | 3 |
| us-mi | policy | `2026-10-06-w6-tanf-ccdf-docs-mi` | 3 | 85 | 170,083 | 1.7 | 3 |
| us-mn | manual | `2026-10-06-w6-tanf-ccdf-manual-mn` | 2 | 1,861 | 2,739,709 | 11.4 | 11 |
| us-mn | policy | `2026-10-06-w6-tanf-ccdf-docs-mn` | 6 | 100 | 151,932 | 3.3 | 5 |
| us-mn | regulation | `2026-10-06-w6-tanf-ccdf-rules-mn` | 5 | 276 | 54,734 | 0.4 | 4 |
| us-mn | statute | `2026-10-06-w6-tanf-ccdf-statutes-mn` | 6 | 1,265 | 1,686,250 | 3.7 | 4 |
| us-mo | manual | `2026-10-06-w6-tanf-ccdf-manual-mo` | 5 | 32 | 70,654 | 0.6 | 4 |
| us-mo | policy | `2026-10-06-w6-tanf-ccdf-docs-mo` | 3 | 8 | 32,759 | 0.9 | 2 |
| us-mo | regulation | `2026-10-06-w6-tanf-ccdf-rules-mo` | 2 | 68 | 405,309 | 0.5 | 4 |
| us-mo | statute | `2026-10-06-w6-tanf-ccdf-statutes-mo` | 1 | 2 | 13,892 | 0.0 | 2 |
| us-ms | manual | `2026-10-06-w6-tanf-ccdf-manual-ms` | 1 | 82 | 190,360 | 0.7 | 4 |
| us-ms | policy | `2026-10-06-w6-tanf-ccdf-docs-ms` | 5 | 105 | 97,925 | 8.3 | 7 |
| us-ms | statute | `2026-10-06-w6-tanf-ccdf-statutes-ms` | 1 | 3 | 31,487 | 0.0 | 3 |
| us-mt | manual | `2026-10-06-w6-tanf-ccdf-manual-mt` | 4 | 36 | 63,198 | 0.7 | 4 |
| us-mt | policy | `2026-10-06-w6-tanf-ccdf-docs-mt` | 4 | 13 | 19,770 | 1.0 | 5 |
| us-mt | regulation | `2026-10-06-w6-tanf-ccdf-rules-mt-title-37-section-37-78` | - | 53 | 137,554 | 1.1 | 24 |
| us-mt | regulation | `2026-10-06-w6-tanf-ccdf-rules-mt-title-37-section-37-80` | - | 25 | 50,621 | 0.8 | 11 |
| us-nc | manual | `2026-10-06-w6-tanf-ccdf-manual-nc` | 5 | 190 | 306,204 | 1.8 | 3 |
| us-nc | policy | `2026-10-06-w6-tanf-ccdf-docs-nc` | 4 | 290 | 725,402 | 12.1 | 5 |
| us-nc | regulation | `2026-10-06-w6-tanf-ccdf-rules-nc` | 1 | 69 | 59,976 | 0.3 | 3 |
| us-nc | statute | `2026-10-06-w6-tanf-ccdf-statutes-nc` | 1 | 2 | 462 | 0.0 | 3 |
| us-nd | manual | `2026-10-06-w6-ccap-manual-nd` | 137 | 274 | 322,069 | 1.5 | 15 |
| us-nd | manual | `2026-10-06-w6-tanf-ccdf-manual-nd` | 5 | 15 | 40,394 | 0.2 | 3 |
| us-nd | policy | `2026-10-06-w6-tanf-ccdf-docs-nd` | 4 | 80 | 55,711 | 2.1 | 4 |
| us-nd | regulation | `2026-10-06-w6-tanf-ccdf-rules-nd` | 2 | 123 | 173,106 | 0.5 | 4 |
| us-ne | policy | `2026-10-06-w6-tanf-ccdf-docs-ne` | 14 | 491 | 933,490 | 29.5 | 20 |
| us-ne | regulation | `2026-10-06-w6-tanf-ccdf-rules-ne` | 1 | 42 | 64,885 | 1.1 | 4 |
| us-ne | statute | `2026-10-06-w6-tanf-ccdf-statutes-ne` | 7 | 31 | 50,001 | 0.3 | 3 |
| all | | 72 scopes | 467 | 18,235 | 43,399,964 | 1467.3 | 537 |

Extract seconds are the wall time of the last run of each scope (download included). Body text check: every document carries at least 200 characters except the Delaware DSS TANF landing page (93: the page prints one summary line; its detail sits in script-loaded menus) and eight short ND CCAP topics (57-184, the publisher's own short topics).

## Families and what they carry

- **Agency documents (policy, 26 scopes).** Program pages, rate and copay schedules, sliding fee scales, all-county
  letters (CA ACL 15-52 to 26-39, CCB 25-15), action transmittals (MD), state plans and drafts (AL 2021, CT 2021-2023
  draft, DE 2017, DC 2020 draft, MI 2017/2023/2023 rev., NC 2019-2022 draft and 2022-2025, NE 2025 file, NE CCDF plan
  FFY 2019-2021 amended 2020-06-11), legislative-staff reports and testimony (CT OLR, MN House Research, NE Fiscal
  Office, ND HB 2190 testimony, MT LFD, HI DHS reports to the legislature), FAQs and provider handbooks. Taken as
  posted: several are superseded editions (the bundles cite them for historical values); the note in each manifest
  entry or the decision says so where the edition matters.
- **Manuals (13 scopes).** AK CCAP Policies and Procedures (706 pages), GA TANF manual PDF export dated 2026-10-05
  (502 pages) and its PAMMS index, IN DFR chapters 2600/3000/3400 and the CCDF Provider Manual, KS KEESM appendices and
  implementation memos, LA County DPSS ePolicy sections, MI RFT 210/270, MN Combined Manual 12/2021 (1,358 pages) and
  CCAP Policy Manual 07/2023 (502 pages), MO DSS TA manual 0210.015.30.10 and IMs, MO DESE child care manual page
  2010.045.00 and the May 2026 Child Care Subsidy Eligibility Policy Manual, MS CCPP Policy Manual 11/2025, MT child care
  manual sections and TANF 501-1 (2018 prints), NC DCDEE subsidized child care manual chapters, ND TANF archive pages,
  ND CCAP manual letter 3909 and the whole ND CCAP Policy Manual 400-28 (135 topics).
- **Rules (21 scopes: 17 manifests, 4 adapter runs).** Official text for every mirror row except AR (blocked) and CA 5 CCR
  (Westlaw blocked): 89 IAC 112 and 23 IAC 2060 (89 IAC 50 moved there), ARM 37.78 and 37.80, K.A.R. 30-4 (79
  regulations listed effective by rules.ks.gov, many printing only a revocation line), MO 5 CSR 25-200 and 13 CSR 40-2,
  NDAC 75-02-01.2 and 75-02-01.3, F.A.C. 65A-4.220, 10A NCAC 10, LAC Title 67 (whole title docx) and 28:CLXV, 606
  CMR 10.00 and 7.00, 470 IAC 10.3, COMAR 13A.14.06.02/.03/.11/.12, RCSA 17b-749-04/-05/-13, GA 290-2-28, HAR
  17-798.2/798.3 (OCR), KY 922 KAR 2:160 (three LRC documents) and 921 KAR 2:016, MN Rules 3400, 9502.0315,
  9503.0005, IAC 441 ch. 170 and the 01-07-2026 print of ch. 41, the CA MPP EAS legacy PDFs 4/10/12/14EAS (older
  editions than the held DOCX), the Kentucky and Louisiana registers cited, NE 392 NAC whole-title print.
- **Statutes (11 scopes, one of them the WIC bulk run).** Section pages under the adapters' path conventions (`us-az/statute/46-207`,
  `us-ks/statute/39-709`, `us-mo/statute/208.040`, `us-ne/statute/43/43-512`, `us-mn/statute/142E.01`,
  `us-nc/statute/chapter-108a/108a-27-01`), session laws (MD 2022 ch. 525, 2024 ch. 717; MN 2019 1st sp. ch. 9; NE LB
  359, LB 304; MS 2021 SB 2759; ME 131st H.P. 592), the whole Florida chapter 220 at the bundle's PATH-ONLY path
  `us-fl/statute/title-xiv/chapter-220`, and the whole Welfare and Institutions Code (7,137 sections) from the bulk file.
- **Form (1 scope).** CA TEMP 2250 from `manifests/us-ca-official-forms.yaml` (EXTRACT-MANIFEST).

## Held already (32 rows)

CT chapters 319s/319t (title 17b scope of 2026-09-14), DC Code 4-2 subchapter I, DC child care subsidy manual (the
`us-dc-child-care-subsidy-manual.yaml` scope of 2026-07-19), DE DSSM 4000 (four rows and the archive PDF), HI HRS
346-71, IA 441-41.26/41.27, IDAPA 16.06.12 and two Idaho DocView files (the CCDF rate-schedule scope), COMAR 07.03.03.03,
.12, .13 (two rows), .17, 10-144 CMR ch. 331 (four Cornell rows), 10-148 CMR ch. 6, 22 M.R.S. 3762, MI BEM 710, Miss.
Admin. Code tit. 18 pt. 19 (TANF plan scope), 9 CCR 2503-6 3.605, CA WIC 11450.12 and ARM 37.78.420 (both in released,
locked scopes), and Indiana Code title 12, which the benefits group of this wave took whole
(`us-in/statute/2026-10-06-w6-benefits-ssi-statute-us-in-title-12`, not re-extracted).

## OUTREACH (13), ABSENT (7), OUT-OF-SCOPE (6), SKIPPED (0)

- OUTREACH: AZ DES rows 15-18; CA LegInfo bill pages SB 70 (2011), SB 80 (2019), AB 135 (2021), AB 99 (2017); CA 5
  CCR 18078 (Westlaw 403); AR 016.20.98-041 and 208.00.13-001 (SOS rules CAPTCHA); MSDE child care scholarship rates
  page (Cloudflare); Miss. Code 43-17-1 (vendor only).
- ABSENT: epolicy.dpss.lacounty.gov home, CDE MB 25-05, UH Bridge to Hope desk aid, LA 2014 TANF renewal, two MSDE
  filedepot PDFs, the mass.gov October 2023 interim CCFA policies.
- OUT-OF-SCOPE: GBPI explainer, Urban Institute Welfare Rules Databook, CDC urban-rural scheme, Census delineation
  file, the ND Power BI dashboard, the MD FIA AT-IM 2017 directory listing.

## Collisions and choices for the consolidation step

- **AZ ARS 46-207, 46-207.01, 46-292**: `us-az/statute/2026-10-06-w6-tanf-ccdf-statutes-az` holds the same azleg.gov
  pages (same SHA-256) at the same paths as the benefits group's whole-title scope
  `us-az/statute/2026-10-06-w6-benefits-snap-statute-us-az-title-46`. Pick the title-46 scope; the decisions' paths
  are identical, so the bundle joins either way, and this run's AZ scope can be dropped.
- **MO 13 CSR 40-2**: the same Secretary of State PDF (same SHA-256) is in `us-mo/regulation/2026-10-06-w6-tanf-ccdf-
  rules-mo` (section-level, `us-mo/regulation/13-csr/40-2/<nnn>`, the 12 CSR 10-2 convention) and page-level in the
  benefits group's `us-mo/regulation/2026-10-06-w6-benefits-regulation-mo` (`us-mo/regulation/csr/13/40-2/page-N`). One
  carrier to be picked; rows 284-286 cite the section paths of this run.
- **CA WIC bulk scope** `us-ca/statute/2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-WIC` shares
  `us-ca/statute/wic/11450`, `11450.12`, `11451.5`, `11452`, `12200`, `18901.3`, `18901.5` with the released section
  scopes (the 2026-06-25 r2026-09-24 preserve-tables, 2026-06-27 and 2026-07-28 scopes): select the bulk scope in
  place of those three or consolidate. Its source is the 1.29 GB bulk zip (stored once, under the scope).
- **ARM 37.78**: `...-rules-mt-title-37-section-37-78` shares `rule-37-78-420` with the released
  `us-mt/regulation/2026-07-13-recovery`; the two MT scopes of this run and the 2026-09-14 tax scope share the
  `us-mt/regulation` and `title-37` containers. IL: the two IL scopes of this run share `us-il/regulation` with each
  other, the tax scope and the benefits/health wave-6 IL scopes, and `title-089/chapter-iv/subchapter-b` with the
  benefits part 113 scope. Same container-folding as the 2026-09-11 consolidations.
- **CA TEMP 2250** (row 19, PATH-ONLY by bundle path): the bundle path `us-ca/form/official_forms/...` fails the
  citation-path grammar (underscore); taken as `us-ca/form/official-forms/cdss.ca.gov/cdssweb/entres/forms/english/
  temp2250`, the slug the other wave-6 form scopes use. The bundle names this row by path only, so its path needs the
  same rename in the bundle. Likewise row 249 (22 M.R.S. 3762) is held at `us-me/statute/title-22/3762/assistance-
  standards`, not the bundle's `us-me/statute/title-22/3762`.
- Rows that name one section of a whole document join to the section path (MO, ND, GA blocks 2 and 13 of the
  290-2-28 page, 606 CMR 10.00 for 10.02/10.04 which the posted file prints without stable section labels).

## Code changes

- `scripts/build_w6_tanf_ccdf_ak_ne_manifests.py` (new): `probe`, `manifests` (writes the manifests and the decisions
  CSV, verifying every cited path against the corpus root or a lock file), `ks-kar`, `nd-ccap`, `queue`. `ruff check`
  and `ruff format` clean.
- No `src/` change; impact analysis: not run (GitNexus MCP tools not available; no library symbol touched).
- Tests: `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or
  official_documents or queue or citation_path"`: 342 passed, 26 skipped, 23 failed; every failure is a
  `FileNotFoundError` or an artifact-count assertion on another scope's `data/corpus` artifact that the sparse
  worktree does not hold (Armenia, Belgium, NY TANF compatibility, SNAP manual TOC tests, UK pilot, SNAP memo scopes,
  `test_corpus_is_nonempty`), none on the manifests or queue rows of this branch.

## Timing and disk

First command 19:02 EDT, probe 19:20, first extraction batch 19:24-19:33, adapters and official-source rows to 19:55,
reruns for OCR, selectors and titles 20:05-20:20, outputs by 20:30 (about 1.5 hours of the 4-hour box). Disk: 3.2 TB
free at the start and at the end (`df -h /`); the 50 GB stop line was never approached.

## Controller

Selector additions: the 72 scopes of the table (none is signed or locked). Do not add `us-az/statute/2026-10-06-w6-
tanf-ccdf-statutes-az` alongside the benefits title-46 scope; choose between the two MO 13 CSR 40-2 carriers; swap the
CA WIC section scopes for the bulk scope or consolidate; fold the shared IL and MT containers.
