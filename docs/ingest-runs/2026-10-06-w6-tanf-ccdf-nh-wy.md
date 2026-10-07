# Wave 6, group tanf-ccdf-nh-wy: state TANF and CCDF bundle documents, New Hampshire to Wyoming

Date: 2026-10-06 (US Eastern; agent run 19:02 to 20:10 EDT).
Work order: `docs/coverage/program-bundle-gaps-2026-10-06/wave6/tanf-ccdf-nh-wy.csv` (341 rows, 340 Tier 1, 21
jurisdictions) with `wave6/00-common-preamble.md` and `wave6/tanf-ccdf-nh-wy-brief.md` (branch
`analysis/program-bundle-gaps-2026-10-06`, worktree `~/axiom-corpus-worktrees/bundle-gaps`).
Worktree `~/axiom-corpus-worktrees/w6-tanf-ccdf-nh-wy` (sparse, `data/corpus/` excluded, never symlinked), branch
`discovery/ingest-w6-tanf-ccdf-nh-wy` cut from main e16ccb799. Every extraction wrote to the main checkout's corpus root
(`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`); nothing under `data/corpus/` is committed, nothing is signed,
nothing was pushed to R2 or loaded into Supabase.
Disk: `df -h /` 3.2 TiB free at the start and at the end (the 50 GB stop line was never near).
Impact analysis: not run (the GitNexus MCP tools are not available in this session). No library function under `src/`
was changed.

Outputs: this note, `docs/ingest-runs/2026-10-06-w6-tanf-ccdf-nh-wy-decisions.csv` (341 rows, one per work-order row),
62 official-document manifests `manifests/us-<st>-tanf-ccdf-w6-<class>.yaml` written by the new generator
`scripts/build_w6_tanf_ccdf_nh_wy_manifests.py`, the statute-adapter manifest
`manifests/state-statutes-tanf-ccdf-w6-nh-wy.yaml`, one public TLS intermediate under `data/certs/`, and a
`program_bundle_gaps_w6` family on the 21 states' rows of `manifests/ccdf-agent-queue.yaml` and
`manifests/tanf-agent-queue.yaml`.

## Result

67 new scopes (62 official-document scopes, 5 adapter scopes), 8,511 provision rows, 11.9 M characters, 83.6 MB of
retained sources. Every scope reports coverage `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths; the
citation-path grammar gate (`scripts/validate_citation_paths.py` on a tree holding only the 67 new files) is `RESULT: OK`
(8,511 records, 8,511 unique paths).

| action | rows | PRESENT | ALREADY-HELD | OUTREACH | ABSENT | SKIPPED |
|---|---:|---:|---:|---:|---:|---:|
| EXTRACT-MANIFEST | 1 | 0 | 1 | 0 | 0 | 0 |
| FETCH | 191 | 154 | 37 | 0 | 0 | 0 |
| CHECK-PUBLISHER | 31 | 14 | 13 | 3 | 1 | 0 |
| OFFICIAL-SOURCE | 72 | 17 | 27 | 28 | 0 | 0 |
| DEAD-LINK | 25 | 4 | 4 | 15 | 2 | 0 |
| BLOCKED-CHECK | 15 | 15 | 0 | 0 | 0 | 0 |
| VENDOR | 6 | 0 | 6 | 0 | 0 | 0 |
| all | 341 | 204 | 88 | 46 | 3 | 0 |

| jurisdiction | rows | PRESENT | ALREADY-HELD | OUTREACH | ABSENT |
|---|---:|---:|---:|---:|---:|
| us-nh | 9 | 9 | 0 | 0 | 0 |
| us-nj | 15 | 9 | 6 | 0 | 0 |
| us-nm | 14 | 14 | 0 | 0 | 0 |
| us-nv | 12 | 9 | 3 | 0 | 0 |
| us-ny | 20 | 3 | 0 | 17 | 0 |
| us-oh | 17 | 10 | 5 | 2 | 0 |
| us-ok | 23 | 3 | 20 | 0 | 0 |
| us-or | 28 | 4 | 24 | 0 | 0 |
| us-pa | 7 | 5 | 1 | 0 | 1 |
| us-ri | 13 | 11 | 2 | 0 | 0 |
| us-sc | 5 | 3 | 2 | 0 | 0 |
| us-sd | 11 | 9 | 2 | 0 | 0 |
| us-tn | 3 | 2 | 1 | 0 | 0 |
| us-tx | 37 | 8 | 0 | 27 | 2 |
| us-ut | 14 | 9 | 5 | 0 | 0 |
| us-va | 15 | 13 | 2 | 0 | 0 |
| us-vt | 20 | 18 | 2 | 0 | 0 |
| us-wa | 44 | 33 | 11 | 0 | 0 |
| us-wi | 22 | 22 | 0 | 0 | 0 |
| us-wv | 6 | 4 | 2 | 0 | 0 |
| us-wy | 6 | 6 | 0 | 0 | 0 |

## Held check (step 1)

Before any request, every row was searched in the local corpus root: the bundle address against every `source_url`
and URL-valued metadata field of the 21 jurisdictions' inventories (19,480 addresses), and the cited rule or section
number against the citation paths and headings of every provisions file of the jurisdiction. 23 rows matched by
address (OH OAC 5101:1-23-20/-40 and 5180:6-1-02/-10, OR OAR 461 rule versions, the PA Cash Assistance Handbook, the SC
TANF manual, 11 WA WAC 388 sections, the NJ WFNJ PDF); the section search found the rest of the 88 ALREADY-HELD rows (OAC
340:10 and 340:40, OAR 414-175 and 461, ARSD 67:10, R986-200, 218-RICR-20-00-2 and -4, the Vermont Reach Up rules, the
newer editions named below). The unreleased wave-4/5 scopes count: 26 ALREADY-HELD rows point at wave-5 scopes of PR #717
(`2026-09-15-ccdf-subsidy-rules*`).

ALREADY-HELD also covers six rows whose bundle address carries an older edition while the corpus holds the current one
(SC Scholarship policy manual 01/13/2025 -> 2026 revision; NV EP Manual C-140 MTL 06/25 -> MTL 03/26; VA TANF manual
chapter 300 11-20 and the July 2024 combined file -> the ten current chapter files; TN rate table -> the 1.1.26 chart;
WV IMM media/40005 posted 2026-10-05 -> the held media/39948 posting of the same 2,263-page manual), third-party copies
whose official text is held (oregon.public.law, Cornell, okrules.elaws.us, vtlawhelp.org, two Google Drive reposts of NV
C-140), and two dead OKDHS/DHHR pages whose rule or chapter is held. Each row's note says which.

## Publisher access (2026-10-06, 19:10-19:40 EDT)

One probe pass first: 218 distinct addresses (every FETCH, CHECK-PUBLISHER, DEAD-LINK, BLOCKED-CHECK and EXTRACT-MANIFEST
address not held by URL), one host at a time (serial per host, 0.5 s apart, at most 12 hosts in parallel), the extractor's
own client: the corpus user agent first, then the extractor's built-in browser user agent on a block status (the
`_needs_browser_fallback` path of `extract_official_documents`), then curl_cffi `chrome120` only for `www.dhhs.nh.gov` and
`www.nysenate.gov`, whose need is documented (`docs/ingest-runs/2026-09-14-msp-charts-snap-fy2026.md`,
`2026-09-14-state-tax-statute-ty2026.md`). TLS verified throughout (certifi plus the committed `data/certs/*.pem`).

- Answered the plain corpus client (HTTP 200): gc.nh.gov, nj.gov, www.childcarenj.gov (PDFs and the CCAP pages; the
  triage 403 on `Parents/CCAP/ImportantInfo` did not recur), bergencountynj.gov, hca.nm.gov, hsd.state.nm.us,
  nmlegis.gov, srca.nm.gov, nmececd.org, dss.nv.gov / www.dss.nv.gov, dos.ny.gov, codes.ohio.gov, dam.assets.ohio.gov,
  oklahoma.gov, okdhslive.org, secure.sos.state.or.us, www.oregon.gov (DELC), pa.gov, pacodeandbulletin.gov,
  webserver.rilegislature.gov, rilegislature.gov, rules.sos.ri.gov, **dhs.ri.gov** (all eight triage-403 addresses
  answered today), scchildcare.org, scstatehouse.gov, dss.sd.gov, sdlegislature.gov (archived-rule PDFs), tn.gov,
  fhb.hhs.texas.gov, twc.texas.gov (except two dead paths), jobs.utah.gov, budget.lis / law.lis / rga.lis.virginia.gov,
  townhall.virginia.gov, dss.virginia.gov, **www.childcare.virginia.gov** (both triage-403 PDFs answered),
  legislature.vermont.gov, dcf.vermont.gov, outside.vermont.gov, app.leg.wa.gov, lawfilesext.leg.wa.gov, dcyf.wa.gov,
  content.govdelivery.com, docs.legis.wisconsin.gov, dcf.wisconsin.gov, bfa.wv.gov, code.wvlegislature.gov, dfs.wyo.gov,
  rules.wyo.gov, wyoleg.gov, drive.google.com (files the WY DFS page links), wspanhandle.com.
- `chrome120` (documented): www.dhhs.nh.gov (BCDHSC form 2533, SR 24-08) and www.nysenate.gov (SOS 410-U, 410-W): HTTP
  403 to the plain client, 200 with the documented profile.
- Missing intermediate: `ljfo.vermont.gov` serves a leaf issued by GlobalSign RSA OV SSL CA 2018 with a Sectigo chain
  ("unable to get local issuer certificate"). The public intermediate was taken from the leaf's AIA URL
  (`http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt`) and committed as
  `data/certs/globalsign-rsa-ov-ssl-ca-2018.pem` (SHA-256 fingerprint
  B6:76:FF:A3:17:9E:88:12:09:3A:1B:5E:AF:EE:87:6A:E7:A6:AA:F2:31:07:8D:AD:1B:FB:21:CD:28:93:76:4A, valid to 2028-11-21);
  extraction ran with `REQUESTS_CA_BUNDLE` = certifi + the committed intermediates. Verification was never disabled.
- Blocked (OUTREACH; probed once each way, not worked around):
  - `otda.ny.gov`, `ocfs.ny.gov` (13 rows): connection reset (RemoteDisconnected) to the corpus client; HTTP 200 F5/TSPD
    JavaScript challenge ("Please enable JavaScript to view the page content. Your support ID is ...", 7.3 KB) to the
    browser user agent. Same block as the 2026-09-10 and 2026-09-13 probes.
  - `govt.westlaw.com` (NY DOS's NYCRR host, used by `extract-nycrr-parts`): HTTP 403 Cloudflare "Just a moment" for
    the plain client and the adapter's own session (Browse/Index and the known Part 385 browse page). New since the July
    and September NYCRR runs. Blocks 18 NYCRR 352 (4 rows) and the OCFS Parts 404 and 415 alternative.
  - `texas-sos.appianportalsgov.com` (TX SOS Texas Administrative Code, 27 rows): a 2,526-byte client-rendered Appian
    shell; its data URL (`/rules-and-meetings/_/ui?interface=VIEW_TAC_SUMMARY&recordId=...`) answers HTTP 406 "Client
    not supported" to a plain client. The legacy viewer `texreg.sos.state.tx.us` now only says "Site Has Moved" to the
    Appian portal; TWC's own rules page links the portal and posts no chapter 809 copy.
  - `emanuals.jfs.ohio.gov` (2 rows): TCP connect timeout (both clients), as on 2026-09-10 and 2026-09-13.
- Not found (404): dss.sd.gov Subsidy_Manual.pdf, oklahoma.gov earned-income-disregard page, oregon.gov ERDC provider
  guide insert, tn.gov rate/QRIS table, dss.virginia.gov 300_11-20.pdf, dhhr.wv.gov 726 ch11, hhs.texas.gov TWH
  bulletin 19-08, twc.texas.gov /programs/child-care-services and WD 19-24 ch1 (current editions or addresses below).

## Method

All official-document manifests come from `scripts/build_w6_tanf_ccdf_nh_wy_manifests.py`: a static table of the
documents read in the probe pass (title, printed edition/effective date, address), one manifest per (jurisdiction,
document class), version `2026-10-06-w6-tanf-ccdf-<class>-<st>` (`w6-`, the family `tanf-ccdf-<class>` and the state in
every version), `--source-as-of 2026-10-06`. `source_url` is exactly the bundle address wherever that address was the
one fetched; every manifest entry carries the bundle row ids it answers in `metadata.program_bundle_ids`, and the
generator refuses an id that is not in the work order. `expression_date` is the effective date printed on the document
where it prints one (rate charts, plans, register filings, session laws, rule versions), else the publisher's HTTP
Last-Modified, else the source date. Extraction defaults: PDFs page-level, HTML heading blocks over the page's main
content; selectors where the page needed them (`section.laws-body` codes.ohio.gov, `div.nys-openleg-result-text`
nysenate.gov, `article` law.lis.virginia.gov, `#contentWrapper` app.leg.wa.gov RCW, `.WordSection1` gc.nh.gov), each
checked against the probe's cached page before the run. Labeled sections where the publisher prints section labels:
N.J.A.C. 10:15 (the OAL export layout and pattern of the main-branch 10:90 manifest), He-C 6900 (the He-W 700
SNAP-rules pattern of the same publisher, with the heading required to start with a capital so cross-references such as
"He-C 6917.03(k) shall be" do not open a section; 111 sections, the rule-to-statute appendix not taken). The NM Human
Services Register PDF is an image-only scan and runs with `ocr: true`.

Adapters: `extract-washington-wac --only-chapter 110-15` (WAC 110-15 Working Connections and Seasonal Child Care,
114 sections), and `extract-state-statutes` with `manifests/state-statutes-tanf-ccdf-w6-nh-wy.yaml` for Wisconsin
chapters 49 and 990 (`include_subunits: true`, so the bundle's subsection addresses such as 49.155(1m)(c)1d.a. have their
own rows), WV Code 9-9 (West Virginia Works Act) and R.I. Gen. Laws 40-5.2 (Rhode Island Works). All adapters ran with
`workers: 1`. The Wisconsin section pages the bundle cites load only a window of about 89 units of the chapter (49.155
stops at subsection (2) in the page HTML), so the chapter adapter, not the pages, carries the text.

Decisions by document family (the CSV has the row-level notes):

- **State rules (codified).** NJ N.J.A.C. 10:15; NH He-C 6900;
  UT R986-700 (DWS's posting, 6 Cornell rows); PA 55 Pa. Code chapters 3042 and 183 (the chapter PDFs linked from the
  Pennsylvania Code TOC; § 183.94 is inside chapter 183); SC Code of Regulations chapter 114 (R. 114-1140 inside; the
  Legislative Council PDF linked from `coderegs/statmast.php`); VA 22VAC40-295-50, 8VAC20-790-20/-40; WAC 110-15; WI DCF
  101 (chapter PDF linked from the DCF 101.09 page) and its October 2021 register insert; WY Child Care Purchase of
  Service chapter 1 (rules.wyo.gov); NM 8.15.2 NMAC (the part the bundle cites, superseded by 8.9.3) and ECECD's
  integrated 8.9.3 text (Nov. 2025; the SRCA 8.9.3 part is already held); OH 5180:2-16 authenticated rule versions
  (2022-2023, the bundle's editions; the current rules are 5180:6-1, held) and two OAC appendices; SD 67:10:05:03 archived
  versions (four LRC archive PDFs, path suffix `--archived-<id>` beside the held current rule).
- **Statutes and session laws.** WI 49 and 990, WV 9-9, RI 40-5.2 (adapters); WA RCW 43.216.135/.802/.814, 74.04.005,
  74.08A.230; OH R.C. 5107.04 and 5107.10; NY SOS 410-u and 410-w; VT 33 V.S.A. chapter 11 (full chapter page), § 1103,
  § 3512; WY Title 42 (compressed title PDF); session laws NM 2026 SB 241, RI P.L. 2025 ch. 278 art. 10, VT Acts 133
  (2022) and 76 (2023), WA Laws 2018 ch. 40 and 2023 ch. 418 (`us-xx/statute/session-laws/<year>/<id>`, the Oregon
  precedent).
- **Rate, copay and income schedules** (`us-xx/policy/ccdf/rate-schedules/<slug-with-date>`, the 2026-09-13 precedent):
  NH, NJ (3 childcarenj.gov + the Bergen County posting of CC-230), NM (2), OK (Appendices C-4, C-4-B), OR (DELC 7492i),
  PA (MCCA effective 2023-03-01), RI (5), SC (2023-2024 fee scale), SD (3), TN (June 2024 chart), TX (4 TWC BCY25/26
  PSoC and board rates), VA, VT (3), WA (4), WV (2), WY (3 sliding fee scales on the Lead Agency's Google Drive, linked
  from dfs.wyo.gov's Child Care page). Older editions the bundle names sit beside the current ones under dated slugs.
- **Manuals:** NV Child Care Policy Manual (July 2024) and EP Manual A-1000 (2015); SD Child Care Assistance Policy
  Manual (Aug. 2026); UT obsolete Table 1 pages (2); VA CCSP Guidance Manual (eff. 2025-10-09); VT ESD procedure
  P-2230A; WI Wisconsin Shares Handbook (July 2026); WV Child Care Subsidy Policy Manual (Oct. 2024).
- **Plans and transmittals:** NV TANF State Plan effective 2020-12-31 (the bundle's edition; FFY24 plan held), NV CC PT
  06-25, OH DCY Procedure Letter 21, ODJFS ACTL 297.
- **Rulemaking:** NY State Register 2024-05-01 issue (OCFS child care eligibility notice), WA WSR 16-01-093, 18-09-088,
  21-21-054, 23-23-054, 24-11-019, NM HSR Vol. 41 No. 17 (OCR), WI DCF 201 rule document.
- **Guidance** (agency pages, press releases, FAQs, legislative analyses and reports): the rest, by jurisdiction in the
  scope table. The TWC child care program page is taken at its current address (`/programs/child-care`, linked from the
  TWC home page) for the dead `/programs/child-care-services`.
- **Publisher checks (CHECK-PUBLISHER).** Accepted as official: nmececd.org (ECECD's own site; ececd.nm.gov does not
  resolve), okdhslive.org (OKDHS's online-services site), scchildcare.org (SC DSS Division of Early Care and Education),
  wspanhandle.com (the Panhandle workforce development board, which administers child care services locally),
  content.govdelivery.com account WADEL (DCYF early learning bulletins; the PowerDMS precedent), drive.google.com files
  linked from dfs.wyo.gov (the 2026-09-10 WY CCDF plan precedent). Not official: oregon.public.law (OAR text held),
  bccap.org (resolved to childcarenj.gov's current rate PDF), chsofnj.org (a CCR&R repost of DFD form CC-1;
  childcarenj.gov posts no CC-1, so the row points at N.J.A.C. 10:15, the rule behind the form), pakeys.org (ABSENT),
  vtlawhelp.org (the Reach Up rules behind it are held), two NV Google Drive reposts (C-140 held).

## Scopes

Seconds are the wall time of one extraction call, download included; source KB is the retained snapshot.

| scope (jurisdiction/class/version) | documents | rows | chars | seconds | source KB |
|---|---:|---:|---:|---:|---:|
| `us-nh/guidance/2026-10-06-w6-tanf-ccdf-guidance-nh` | 1 | 2 | 7,324 | 4 | 106 |
| `us-nh/policy/2026-10-06-w6-tanf-ccdf-policy-nh` | 1 | 3 | 6,522 | 4 | 968 |
| `us-nh/regulation/2026-10-06-w6-tanf-ccdf-regulation-nh` | 1 | 112 | 369,916 | 4 | 2,250 |
| `us-nj/guidance/2026-10-06-w6-tanf-ccdf-guidance-nj` | 1 | 10 | 20,605 | 4 | 141 |
| `us-nj/policy/2026-10-06-w6-tanf-ccdf-policy-nj` | 4 | 19 | 40,927 | 4 | 3,323 |
| `us-nj/regulation/2026-10-06-w6-tanf-ccdf-regulation-nj` | 1 | 55 | 154,282 | 3 | 1,962 |
| `us-nm/guidance/2026-10-06-w6-tanf-ccdf-guidance-nm` | 8 | 136 | 135,839 | 42 | 16,808 |
| `us-nm/policy/2026-10-06-w6-tanf-ccdf-policy-nm` | 2 | 14 | 19,618 | 3 | 4,725 |
| `us-nm/regulation/2026-10-06-w6-tanf-ccdf-regulation-nm` | 2 | 25 | 153,091 | 4 | 668 |
| `us-nm/rulemaking/2026-10-06-w6-tanf-ccdf-rulemaking-nm` | 1 | 5 | 5,746 | 7 | 585 |
| `us-nm/statute/2026-10-06-w6-tanf-ccdf-statute-nm` | 1 | 22 | 27,371 | 4 | 75 |
| `us-nv/guidance/2026-10-06-w6-tanf-ccdf-guidance-nv` | 5 | 32 | 10,232 | 6 | 203 |
| `us-nv/manual/2026-10-06-w6-tanf-ccdf-manual-nv` | 2 | 168 | 437,551 | 5 | 2,739 |
| `us-nv/policy/2026-10-06-w6-tanf-ccdf-policy-nv` | 2 | 62 | 153,668 | 3 | 2,453 |
| `us-ny/rulemaking/2026-10-06-w6-tanf-ccdf-rulemaking-ny` | 1 | 117 | 663,716 | 5 | 1,123 |
| `us-ny/statute/2026-10-06-w6-tanf-ccdf-statute-ny` | 2 | 4 | 12,711 | 4 | 77 |
| `us-oh/guidance/2026-10-06-w6-tanf-ccdf-guidance-oh` | 2 | 9 | 32,455 | 4 | 1,412 |
| `us-oh/regulation/2026-10-06-w6-tanf-ccdf-regulation-oh` | 6 | 50 | 57,062 | 5 | 1,563 |
| `us-oh/statute/2026-10-06-w6-tanf-ccdf-statute-oh` | 2 | 4 | 8,431 | 3 | 39 |
| `us-ok/policy/2026-10-06-w6-tanf-ccdf-policy-ok` | 3 | 11 | 20,214 | 8 | 624 |
| `us-or/guidance/2026-10-06-w6-tanf-ccdf-guidance-or` | 2 | 40 | 23,260 | 4 | 260 |
| `us-or/policy/2026-10-06-w6-tanf-ccdf-policy-or` | 1 | 8 | 13,373 | 3 | 843 |
| `us-pa/guidance/2026-10-06-w6-tanf-ccdf-guidance-pa` | 2 | 15 | 19,784 | 3 | 1,263 |
| `us-pa/policy/2026-10-06-w6-tanf-ccdf-policy-pa` | 1 | 4 | 7,779 | 3 | 87 |
| `us-pa/regulation/2026-10-06-w6-tanf-ccdf-regulation-pa` | 2 | 130 | 306,792 | 3 | 386 |
| `us-ri/guidance/2026-10-06-w6-tanf-ccdf-guidance-ri` | 4 | 26 | 17,252 | 4 | 415 |
| `us-ri/policy/2026-10-06-w6-tanf-ccdf-policy-ri` | 5 | 11 | 8,862 | 4 | 1,782 |
| `us-ri/statute/2026-10-06-w6-tanf-ccdf-statute-ri` | 1 | 2 | 64,237 | 4 | 149 |
| `us-ri/statute/2026-10-06-w6-tanf-statute-ri-us-ri-chapter-40-5.2` | adapter | 41 | 99,463 | 9 | 330 |
| `us-sc/policy/2026-10-06-w6-tanf-ccdf-policy-sc` | 1 | 2 | 1,875 | 4 | 253 |
| `us-sc/regulation/2026-10-06-w6-tanf-ccdf-regulation-sc` | 1 | 268 | 977,626 | 4 | 701 |
| `us-sd/manual/2026-10-06-w6-tanf-ccdf-manual-sd` | 1 | 56 | 157,234 | 4 | 752 |
| `us-sd/policy/2026-10-06-w6-tanf-ccdf-policy-sd` | 3 | 6 | 6,343 | 4 | 365 |
| `us-sd/regulation/2026-10-06-w6-tanf-ccdf-regulation-sd` | 4 | 8 | 5,173 | 4 | 156 |
| `us-tn/guidance/2026-10-06-w6-tanf-ccdf-guidance-tn` | 1 | 6 | 7,630 | 4 | 78 |
| `us-tn/policy/2026-10-06-w6-tanf-ccdf-policy-tn` | 1 | 3 | 4,210 | 4 | 158 |
| `us-tx/guidance/2026-10-06-w6-tanf-ccdf-guidance-tx` | 4 | 47 | 48,515 | 4 | 934 |
| `us-tx/policy/2026-10-06-w6-tanf-ccdf-policy-tx` | 4 | 62 | 131,977 | 4 | 1,805 |
| `us-ut/guidance/2026-10-06-w6-tanf-ccdf-guidance-ut` | 1 | 3 | 4,735 | 4 | 2,015 |
| `us-ut/manual/2026-10-06-w6-tanf-ccdf-manual-ut` | 2 | 7 | 988 | 4 | 41 |
| `us-ut/regulation/2026-10-06-w6-tanf-ccdf-regulation-ut` | 1 | 20 | 94,019 | 3 | 170 |
| `us-va/guidance/2026-10-06-w6-tanf-ccdf-guidance-va` | 8 | 306 | 683,386 | 12 | 2,747 |
| `us-va/manual/2026-10-06-w6-tanf-ccdf-manual-va` | 1 | 207 | 500,947 | 5 | 2,420 |
| `us-va/policy/2026-10-06-w6-tanf-ccdf-policy-va` | 1 | 3 | 3,429 | 4 | 190 |
| `us-va/regulation/2026-10-06-w6-tanf-ccdf-regulation-va` | 3 | 6 | 23,236 | 5 | 134 |
| `us-vt/guidance/2026-10-06-w6-tanf-ccdf-guidance-vt` | 7 | 111 | 234,911 | 5 | 3,332 |
| `us-vt/manual/2026-10-06-w6-tanf-ccdf-manual-vt` | 1 | 7 | 5,223 | 4 | 440 |
| `us-vt/policy/2026-10-06-w6-tanf-ccdf-policy-vt` | 3 | 6 | 4,571 | 4 | 236 |
| `us-vt/statute/2026-10-06-w6-tanf-ccdf-statute-vt` | 5 | 123 | 225,362 | 5 | 737 |
| `us-wa/guidance/2026-10-06-w6-tanf-ccdf-guidance-wa` | 2 | 4 | 5,908 | 3 | 98 |
| `us-wa/policy/2026-10-06-w6-tanf-ccdf-policy-wa` | 4 | 9 | 6,080 | 5 | 887 |
| `us-wa/regulation/2026-10-06-w6-ccdf-rules-wa-110-15` | adapter | 117 | 151,975 | 9 | 935 |
| `us-wa/rulemaking/2026-10-06-w6-tanf-ccdf-rulemaking-wa` | 5 | 10 | 19,303 | 5 | 373 |
| `us-wa/statute/2026-10-06-w6-tanf-ccdf-statute-wa` | 7 | 31 | 67,672 | 6 | 762 |
| `us-wi/guidance/2026-10-06-w6-tanf-ccdf-guidance-wi` | 1 | 11 | 25,442 | 3 | 144 |
| `us-wi/manual/2026-10-06-w6-tanf-ccdf-manual-wi` | 1 | 204 | 469,229 | 6 | 1,350 |
| `us-wi/regulation/2026-10-06-w6-tanf-ccdf-regulation-wi` | 2 | 41 | 286,364 | 5 | 552 |
| `us-wi/rulemaking/2026-10-06-w6-tanf-ccdf-rulemaking-wi` | 1 | 8 | 13,291 | 3 | 40 |
| `us-wi/statute/2026-10-06-w6-tanf-ccdf-statute-wi-chapter-49` | adapter | 5,198 | 3,973,593 | 11 | 4,749 |
| `us-wi/statute/2026-10-06-w6-tanf-ccdf-statute-wi-chapter-990` | adapter | 122 | 51,269 | 5 | 513 |
| `us-wv/manual/2026-10-06-w6-tanf-ccdf-manual-wv` | 1 | 142 | 344,060 | 5 | 598 |
| `us-wv/policy/2026-10-06-w6-tanf-ccdf-policy-wv` | 2 | 9 | 6,826 | 4 | 34 |
| `us-wv/statute/2026-10-06-w6-tanf-statute-wv-us-wv-chapter-9-article-9` | adapter | 24 | 32,025 | 7 | 4,295 |
| `us-wy/guidance/2026-10-06-w6-tanf-ccdf-guidance-wy` | 1 | 7 | 125,273 | 5 | 227 |
| `us-wy/policy/2026-10-06-w6-tanf-ccdf-policy-wy` | 3 | 6 | 5,209 | 7 | 266 |
| `us-wy/regulation/2026-10-06-w6-tanf-ccdf-regulation-wy` | 1 | 41 | 75,542 | 5 | 210 |
| `us-wy/statute/2026-10-06-w6-tanf-ccdf-statute-wy` | 1 | 133 | 256,200 | 5 | 527 |

## What stays OUTREACH or ABSENT

| status | rows | documents | reason |
|---|---:|---|---|
| OUTREACH | 27 | TX TAC 1 TAC 372 (TANF; 16 Cornell section rows and subchapter B), 40 TAC 809 (5 Cornell + 1 Justia), 26 TAC 746.1601, and the 3 SOS portal addresses | the official TAC is published only through the client-rendered Appian portal (406 "Client not supported" to a plain client); needs a static or bulk export from the Texas Secretary of State |
| OUTREACH | 13 | NY OTDA ADMs 97-ADM-17, 97-ADM-23, 22-ADM-11, 23-ADM-04, 24-ADM-04, 25-ADM-04, GIS 22 DC052; OCFS 22-OCFS-ADM-18, 23-OCFS-ADM-18, 24-OCFS-LCM-22, 19-OCFS-LCM-23 and the Part 404/415 regulation PDFs | F5/TSPD JavaScript challenge / connection reset, durable across 2026-09-10, 09-13 and 10-06 |
| OUTREACH | 4 | 18 NYCRR Part 352 (Cornell 352, 352.1-352.3) | govt.westlaw.com (DOS's NYCRR host) now answers a Cloudflare challenge; the NYCRR adapter cannot run |
| OUTREACH | 2 | ODJFS eManuals CAM ACT index and ACT-262 | host unreachable (TCP timeout), durable |
| ABSENT | 1 | PA MCCA chart effective 2025-01-01 (pakeys.org) | pakeys.org is OCDEL's contractor, not the publisher; pa.gov's ELRC and child care pages link no 2025 chart (the 2023-03-01 pa.gov chart is taken) |
| ABSENT | 1 | TX TWH bulletin 19-08 (2020) | 404; the TWH Policy Bulletins page on fhb.hhs.texas.gov lists no 2020 bulletin 19-08 |
| ABSENT | 1 | TX WD Letter 19-24, Change 1 | 404; on neither TWC's current nor rescinded policy-letter list; its Attachment 1 (BCY2025 rates) is taken |

No row is SKIPPED: the work order was finished in about 70 minutes of the 4-hour box.

## Locked-scope recheck (controller correction, 2026-10-06)

The controller ruled mid-run that scopes committed on main only as lock files
(`.axiom/corpus-locks/<jur>/<class>/<version>.json`) count as held. For the 21 jurisdictions, 410 lock files exist; 8 of
them name scopes whose bytes are not in the corpus root (NJ NJDOL contribution rates and two payroll statute titles, NY
IT-214 and the Tax Law line-structure re-version, VA 22VAC40-601 SNAP, WI Schedule SB and the chapter-71 subunit
re-version); none is a TANF or CCDF document of this work order (their source file names were read). Every other locked
scope is on disk and was already in the held check. The sha256 of each of the 203 source files of the new scopes was then
looked up in all 42,848 locked source entries: two matches.

1. `WFNJ_Manual_12.17.24.pdf` (N.J.A.C. 10:90) is byte-identical to the source of the locked
   `us-nj/regulation/2026-07-13-recovery` scope, which holds it page-level (`us-nj/regulation/recovery/us-nj-njac-10-90`)
   with section alias rows for 10:90-3.2, 3.3, 3.8, 3.9, 3.19 and 3.20. The section-level 10:90 document was dropped from
   `manifests/us-nj-tanf-ccdf-w6-regulation.yaml`, the NJ regulation scope was re-extracted with N.J.A.C. 10:15 alone, and
   the EXTRACT-MANIFEST row and the five Cornell 10:90 rows are ALREADY-HELD with the recovery scope (the six-path
   collision with it is gone too). The main-branch manifest `manifests/us-nj-wfnj-rules.yaml` and its path
   `us-nj/regulation/njac-10-90` remain for a successor of the recovery scope.
2. The Rhode Island adapter's retained Statutes root index page (`Statutes.html`) is the page the locked RI chapter
   44-30 scope also keeps; it is an index page, not a document, and stays.

Address and path checks of the 62 manifests' `source_url`s against every inventory in the corpus root found nothing
else.

## Controller: collisions and swaps

Every new scope's citation paths were intersected with every other provisions file of the same jurisdiction and class in
the corpus root (released and unreleased). Two scopes share paths with existing scopes:

| new scope | shares | with | route |
|---|---|---|---|
| `us-wi/statute/2026-10-06-w6-tanf-ccdf-statute-wi-chapter-49` | `us-wi/statute/49.77`, `us-wi/statute/49.471` | `us-wi/statute/2026-09-15-ssi-state-supplement-rules` (wave 5 SSI, PR #717) and `us-wi/statute/2026-10-06-w6-health-statute-wi` (wave 6 health agent) | both carry a body-less root plus one child; the whole-chapter scope carries the section text: swap the single-section scopes out, or consolidate (the 49.77 manifest's own note anticipates this) |
| `us-wa/regulation/2026-10-06-w6-ccdf-rules-wa-110-15` | the container `us-wa/regulation` | every WAC adapter scope (388-400, -424, -450, -470, -474, -478, and the wave-6 health agent's 182-505/182-512) | the shared title container the WAC adapter emits in every scope; the existing consolidation handles it |

The NV EP Manual chapter C-140 the bundle names was first extracted and then dropped from the NV manual manifest: its
path `us-nv/manual/dwss/eligibility-payments/c-140` is held in a newer edition (MTL 03/26) by
`us-nv/manual/2026-09-11-nv-snap-manual-supersede`; the three C-140 rows are ALREADY-HELD.

Selector additions (all unsigned, on the controller's disk): the 67 scopes of the scope table. No released scope is
superseded except through the collision routes above. Not done here: `sign-ingest-manifest`, `corpus push`, any
selector, Supabase.

## Code changes

- `scripts/build_w6_tanf_ccdf_nh_wy_manifests.py` (new): the document table, the manifest writer (`--only`) and the queue
  family writer (`--queue`, reads the decisions file). `ruff check` clean.
- `manifests/state-statutes-tanf-ccdf-w6-nh-wy.yaml` (new): WI 49 and 990, WV 9-9, RI 40-5.2 adapter sources.
- 62 generated manifests `manifests/us-<st>-tanf-ccdf-w6-<class>.yaml`.
- `manifests/ccdf-agent-queue.yaml`, `manifests/tanf-agent-queue.yaml`: one `program_bundle_gaps_w6` entry under
  `additional_families` for each of the 21 states (a load/dump round trip of both files is byte-identical, so only those
  entries change).
- `data/certs/globalsign-rsa-ov-ssl-ca-2018.pem` (public intermediate, `git add -f`).
- No change under `src/` or `tests/`.

## Checks

- Coverage re-read for all 67 scopes: `complete: true`, no duplicate path, no missing or extra inventory entry.
- `uv run python scripts/validate_citation_paths.py --provisions <tree of the 67 new files>`: `RESULT: OK`. The new files
  add 2,381 `page-N`, 312 `block-N`, 111 space and 117 uppercase segments (He-C section labels such as
  `us-nh/regulation/he-c-6900/He-C 6910.06` follow the He-W 700 precedent; `us-ny/statute/SOS/410-U` the NY Tax Law
  precedent); the tree-wide ratchets are the controller's to move at the release cut.
- `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or
  official_documents or discovery"`: 308 passed, 2 skipped, 17 failed. Every failure is a `FileNotFoundError` (or the
  WI pit-west replay assertion that follows from one) on another scope's `data/corpus` artifact that the sparse worktree
  does not hold: Armenia ARLIS, BE promotion (2), NY TANF compatibility (2), WI pit-west replay, Israel openlaw, AK/CT/MI/
  MT/ND/NY SNAP manuals, the SNAP child-support CA/DE sources (4). Without `AXIOM_CORPUS_PARTIAL_TESTS` the suite exits at
  collection (56,318 locked files absent).

## Timing

Probe pass about 5 minutes (218 addresses). Extraction: the 62 official-document manifests ran 7 jurisdictions at a time,
manifests of one jurisdiction serially, in about 60 seconds of wall time (3-12 s each; NM guidance 42 s, its 15 MB
parents' guide); the adapters 5-11 s each. Re-runs: NH regulation (section split), PA policy (MCCA edition and slug), TX
guidance (TWC program page), NV manual (C-140 dropped), NJ regulation (10:90 dropped, see the locked-scope recheck); each into its own version after removing the scope's stale
source files.

## Note for the other agents

The session scratchpad directory is shared by the wave-6 agents; for the first 15 minutes this run wrote helper files
(`probe.py`, `grepcorp.py`, `urlindex.py`, `urlidx.json`, `probe_urls*.txt`) into the shared `scratchpad/w6/` folder, which
another agent also uses, before moving to `scratchpad/w6-tanf-ccdf-nh-wy/`. If an agent's `scratchpad/w6/probe.py` or
`urlidx.json` looks foreign, this run overwrote it.

## Rebuild

```bash
cd ~/axiom-corpus-worktrees/w6-tanf-ccdf-nh-wy
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
cat $(uv run python -c "import certifi;print(certifi.where())") data/certs/*.pem > /tmp/w6-ca.pem
export REQUESTS_CA_BUNDLE=/tmp/w6-ca.pem
uv run python scripts/build_w6_tanf_ccdf_nh_wy_manifests.py           # 62 manifests
for f in manifests/us-*-tanf-ccdf-w6-*.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B \
    --version $(grep '^version:' $f | awk '{print $2}') --manifest $f --source-as-of 2026-10-06
done
for s in us-wi-statutes-chapter-49 us-wi-statutes-chapter-990 us-wv-code-chapter-9-article-9 \
         us-ri-general-laws-chapter-40-5-2; do
  uv run axiom-corpus-ingest extract-state-statutes --base $B \
    --manifest manifests/state-statutes-tanf-ccdf-w6-nh-wy.yaml --only-source-id $s
done
uv run axiom-corpus-ingest extract-washington-wac --base $B --version 2026-10-06-w6-ccdf-rules-wa \
  --only-chapter 110-15 --source-as-of 2026-10-06 --workers 1
uv run python scripts/build_w6_tanf_ccdf_nh_wy_manifests.py --queue   # after the decisions file
```
