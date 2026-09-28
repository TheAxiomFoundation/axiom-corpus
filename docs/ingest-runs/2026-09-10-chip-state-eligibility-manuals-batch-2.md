# CHIP state eligibility manuals, handbook chapters and adopted rules, batch 2

Date: 2026-09-10
Program: CHIP (board Year 1 list; `manifests/chip-agent-queue.yaml`)
Branch: `discovery/ingest-chip` (continues docs/ingest-runs/2026-09-10-chip-state-eligibility-manuals.md)

Timing: started_at 2026-09-10T18:33:42Z, finished_at 2026-09-10T19:03:38Z, agent wall time 29 min 56 s.
GitNexus impact analysis was not run: the GitNexus MCP tools were not available in this
session. No adapter or library function was modified. The only code change is in the batch-1
generator script `scripts/build_chip_state_eligibility_manifests.py`: batch-2 dictionaries
(`CONFIRMED_BATCH2`, `BLOCKED_BATCH2`, `DONE_BATCH2`, `RETRY_NOTES`) and four small edits to its
`main()` so it creates queue rows for jurisdictions that were not on the lead list, writes
`index_families` and `pointer`, and appends the retry note to the batch-1 blocked rows. Batch-1
manifests regenerate byte-identical. `uv run ruff check scripts/build_chip_state_eligibility_manifests.py`
passes; `uv run ruff check scripts/` additionally reports 8 pre-existing findings in two scripts
this run did not touch (`build_liheap_state_plan_manifests.py` F401; `draft_program_work_orders.py`
E401/I001/F401/E701/E702), left as they are.

Source family and conventions are batch 1's: the state agency's own CHIP eligibility manual,
handbook chapter, or adopted eligibility rule (or the combined Medicaid eligibility manual
chapters that govern CHIP), confirmed from the publisher's own index; document_class `manual`
(or `regulation` for an adopted rule); version `2026-09-10-chip-state-eligibility-manual`;
citation paths `us-xx/manual/<agency>/chip/<section>`, regulation scopes following each
jurisdiction's existing regulation citation convention. CMS state plan amendments were not
re-ingested.

Work order: the next ten states not in the queue, by population (CA, PA, OH, NC, NJ, VA, WA,
AZ, TN, MD). NC, NJ and VA are already covered by combined Medicaid eligibility manuals that
the parallel Medicaid run (branch `discovery/ingest-medicaid`, same corpus root) ingested on
2026-09-10, so they were marked done by pointer and CO, MN and SC were pulled. Batch-1 blocked
rows FL, KS, LA, WI were retried once each.

## Result

| Jurisdiction | Status | Scope | Index docs | Taken | Provisions | Extract s |
|---|---|---|---|---|---|---|
| us-ca | blocked_primary_source | - | n/a (403) | 0 | - | - |
| us-pa | agent_ready | us-pa/manual | 16 | 1 | 6 | 3 |
| us-oh | blocked_primary_source | - | n/a (connect timeout) | 0 | - | - |
| us-nc | done (pointer, Medicaid run) | us-nc/manual (medicaid) | 64 | 0 | - | - |
| us-nj | done (pointer, Medicaid run) | us-nj/manual (medicaid) | 6 | 0 | - | - |
| us-va | done (pointer, Medicaid run) | us-va/manual (medicaid) | 21 | 0 | - | - |
| us-wa | agent_ready | us-wa/manual | 16 | 1 | 4 | 3 |
| us-az | blocked_primary_source | - | n/a (403) | 0 | - | - |
| us-tn | agent_ready | us-tn/regulation | 22 | 1 | 11 | 2 |
| us-md | agent_ready | us-md/regulation | 17 | 17 | 34 | 1 |
| us-co | agent_ready | us-co/regulation | 22 | 1 | 26 | 4 |
| us-mn | agent_ready | us-mn/manual | 23 | 2 | 13 | 2 |
| us-sc | blocked_primary_source | - | n/a (403 after chain repair) | 0 | - | - |

Attempted 13 rows; extracted 6 jurisdictions (23 documents, 94 provisions); blocked 4;
done-by-pointer 3. Index documents found on the six extracted publishers' indexes: 116; taken 23.
Coverage `complete: true` for every extracted scope, 0 missing, 0 extra, 0 duplicate citation
paths. Uniqueness was re-verified directly on each provisions JSONL, and every new citation path
was checked against every other provisions JSONL under `data/corpus/provisions/<jurisdiction>/`
(0 cross-scope collisions). Every inventory item names an existing non-symlink source file.
Smoke runs (scratch base) for all six scopes preceded the full runs; the only change between
smoke and full run was the WA heading pattern (the WAC number is now kept in the heading).
Extract seconds are wall seconds of the final `extract-official-documents` command.
Queue status_counts after this batch: done 6, agent_ready 17, blocked_primary_source 8.

Retries of the batch-1 blocked rows (one plain request, one chrome120 request, 25 s timeouts,
2026-09-10T18:39Z): FL https://ahca.myflorida.com/medicaid/florida-kidcare HTTP 403 Cloudflare
"Attention Required!" both ways; KS https://www.kancare.ks.gov/policies-and-reports/eligibility-policy
HTTP 403 "Access Denied" both ways; LA https://ldh.la.gov/page/medicaid-eligibility-manual HTTP 403
Cloudflare both ways; WI https://www.emhandbooks.wisconsin.gov/bcplus/bcplus.htm TCP connect
timeout after 25 s both ways. Each row note now ends "retried 2026-09-10T18:39Z, same failure (...)".

Artifacts (unsigned, uncommitted, awaiting controller; `data/corpus` lives in the main
checkout, the worktree is sparse):

- `data/corpus/sources/us-xx/<class>/2026-09-10-chip-state-eligibility-manual/official-documents/*`
- `data/corpus/inventory/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`
- `data/corpus/provisions/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.jsonl`
- `data/corpus/coverage/us-xx/<class>/2026-09-10-chip-state-eligibility-manual.json`

for us-pa, us-wa, us-mn (manual) and us-tn, us-md, us-co (regulation).

TLS: verification was never disabled. img1.scdhhs.gov and www1.scdhhs.gov (South Carolina
MPPM) serve their leaf certificate without the issuing intermediate; the publisher's public
intermediate "Go Daddy Secure Certificate Authority - G2" (fetched from the leaf's AIA URL
http://certificates.godaddy.com/repository/gdig2.crt, SHA-256
97:3A:41:27:6F:FD:01:E0:27:A2:AA:D4:9E:34:C3:78:46:D3:E9:76:FF:6A:62:0B:67:12:E3:38:32:04:1A:A6)
is added as `data/certs/godaddy-secure-certificate-authority-g2.pem` and was used through
REQUESTS_CA_BUNDLE (certifi + that file); the chain then verifies (openssl "Verify return
code: 0"), after which the hosts return HTTP 403, so SC is blocked, not a TLS problem. No other
publisher needed a chain fix. Hosts that 403 plain clients and were read through the existing
manifest `request: browser_impersonation: true` fallback: publications.tnsosfiles.com.

Rebuild:

```bash
uv run python scripts/build_chip_state_eligibility_manifests.py
for j in pa wa tn md co mn; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-chip-state-eligibility-manual \
    --manifest manifests/us-$j-chip-state-eligibility-manual.yaml --source-as-of 2026-09-10
done
```

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. The 10 failures are the known sparse-worktree failures
(BE rulespec promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP
manual tests), all `data/corpus` artifacts absent from this worktree; none touch CHIP files.

## Per-jurisdiction index inventories

- **us-ca** (blocked) DHCS Medi-Cal Eligibility Procedures Manual index
  https://www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx: www.dhcs.ca.gov returns
  HTTP 403 with an empty 772-byte body for the MEPM page and for the site root, to a plain
  client, the WebFetch client and the chrome120 browser-impersonation client. California's CHIP is
  Title XXI-funded Medi-Cal for children (OTLIC) plus MCAP and county CCHIP; 22 CCR is
  vendor-hosted (Westlaw) and was not used. 0 taken.
- **us-pa** DHS CHIP Resources index https://www.pa.gov/agencies/dhs/resources/chip/chip-resources:
  16 documents. Families: agency policy handbook PDFs 2 (CHIP Enrollment and Benefits Handbook,
  released 2026-01-01, 55 pp; CHIP Procedures Handbook, January 2026, 148 pp), CHIP State Plan PDF
  1 (September 2026), privacy notice PDF 1, CHIP program web pages 12 (CHIP, About, Coverage,
  Insurance Companies, Resources, FAQ, Eligibility and Benefits, E-Toolkit, Order Materials,
  Annual Reports, Advisory Council, Contact). Taken 1: the Enrollment and Benefits Handbook,
  chapter-level (5 chapters: eligibility, enrollment, cost sharing, benefit package, dental).
  Not taken: the Procedures Handbook (MCO operating procedures), the state plan (state-plan
  family), the privacy notice. The Medicaid run's MA Eligibility Handbook section 309.6 in
  us-pa/manual only refers applicants to CHIP. The 2017 "CHIP Eligibility and Benefits Handbook"
  URL that search engines still list returns 404.
- **us-oh** (blocked) OAC Chapter 5160:1-4 index
  https://codes.ohio.gov/ohio-administrative-code/chapter-5160:1-4: codes.ohio.gov did not accept
  TCP connections on 443 (requests ConnectTimeout 25 s plain; curl (28) timeout 25 s chrome120;
  WebFetch ECONNREFUSED 198.234.74.32:443); emanuals.jfs.ohio.gov timed out the same way;
  medicaid.ohio.gov answered but publishes no eligibility manual. Ohio's CHIP is a Medicaid
  expansion governed by those rules. codes.ohio.gov served us-oh-snap-rules.yaml in July 2026, so
  probably transient. 0 taken.
- **us-nc** (done by pointer) Family and Children's Medicaid manual index
  https://policies.ncdhhs.gov/divisional/health-benefits-nc-medicaid/family-and-childrens-medicaid/
  (403 to the WebFetch client; count from the Medicaid run's inventory): 64 F&C documents
  (MA-3100 ... MA-3570 plus the F&C table of contents), all in
  `us-nc/manual/dhb/medicaid/ma-3xxx`, version 2026-09-10-medicaid-state-eligibility-manual. NC
  Health Choice was folded into Medicaid on 2023-04-01; nothing separate to add.
- **us-nj** (done by pointer) DHS/DMAHS rules PDF set
  https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/ (6 chapters: N.J.A.C.
  10:69, 10:70, 10:71, 10:72, 10:78, 10:79). N.J.A.C. 10:79 NJ FamilyCare-Children's Program (the
  CHIP rule) is `us-nj/manual/dhs/medicaid/njac-10-79`, 115 page provisions, from the Medicaid
  run. The HTML index page for that folder was not re-located (three candidate URLs 404).
- **us-va** (done by pointer) DMAS Virginia Medical Assistance Eligibility Manual (21 chapters in
  the Medicaid run's inventory): Chapter M21 FAMIS is `us-va/manual/dmas/medicaid/m21` (22
  provisions), with M22 FAMIS MOMS and M23 FAMIS Prenatal Coverage alongside.
- **us-wa** HCA Apple Health Eligibility Manual, MAGI-based programs manual index
  https://www.hca.wa.gov/free-or-low-cost-health-care/i-help-others-apply-and-access-apple-health/modified-adjusted-gross-income-magi-based-programs-manual:
  16 chapters. Families: MAGI program chapters 9 (Alien Emergency Medical; Adults; Kids with and
  without premiums; parents and caretakers; pregnant individuals; medical extension; health care
  for adults / children / pregnant individuals), MAGI financial eligibility chapters 3 (household
  composition, income parts 1-2), MAGI client notice chapters 4 (500/600 series reason codes,
  client notices overview, Healthplanfinder letters). Taken 1: "Apple Health for Kids, with and
  without premiums" (revised 2026-04-01), sectioned by WAC 182-505-0210, -0215, -0225; the
  accordion title copies of each WAC heading are dropped so each WAC appears once; HCA's
  clarifying information follows the WAC it annotates.
- **us-az** (blocked) AHCCCS Eligibility Policy Manual host https://epm.azahcccs.gov/ (KidsCare
  is chapter 408), www.azahcccs.gov (AMPM index, program pages, site root): HTTP 403 Forbidden to
  plain, WebFetch and chrome120 clients. The adopted KidsCare rule A.A.C. Title 9 Chapter 31 at the
  Secretary of State (apps.azsos.gov/public_services/Title_09/9-31.pdf) returns a Cloudflare
  JavaScript challenge ("Just a moment...", HTTP 403). 0 taken.
- **us-tn** Tennessee Secretary of State effective rules index for Chapter 1200-13 (Division of
  TennCare) https://publications.tnsosfiles.com/rules/1200/1200-13/1200-13.htm: 22 rule chapters
  1200-13-01 to 1200-13-22 (one family, TennCare rule chapter PDFs). Taken 1: 1200-13-21
  CoverKids, February 2025 revision, rules .01-.10. Not taken: 1200-13-20 TennCare Eligibility
  (Medicaid) and the rest. tn.gov returns 403 to plain and chrome120 clients;
  publications.tnsosfiles.com needs browser impersonation.
- **us-md** COMAR 10.09.11 Maryland Children's Health Program chapter page
  https://regs.maryland.gov/us/md/exec/comar/10.09.11 (Division of State Documents;
  dsd.maryland.gov 301-redirects there): 17 regulation sections, 15 in force and 2 repealed
  (.08, .09). Taken 17 (one HTML document each, `article.content`). No Medical Assistance
  eligibility manual was located on mdh.maryland.gov.
- **us-co** Colorado Secretary of State CCR list for the HCPF Medical Services Board
  https://www.sos.state.co.us/CCR/NumericalCCRDocList.do?deptID=7&agencyID=69: 22 CCR documents
  (10 CCR 2505-3; 21 parts of 10 CCR 2505-10 Medical Assistance). Taken 1: 10 CCR 2505-3
  (Children's Basic Health Plan / CHP+), current version effective 2026-04-14 (ruleVersionId
  12479), sections 50-610 (25 sections; 100, 200, 300 are title-only containers, 160 and 310 are
  repealed, 610 carries the editor's notes and history). hcpf.colorado.gov returns 403 (CloudFront).
- **us-mn** DHS Health Care Programs Eligibility Policy Manual chapter 2.2 MA-FCA index
  https://hcopub.dhs.state.mn.us/epm/2_2.htm: 23 topic pages (one family). Minnesota's CHIP is
  Medicaid-expansion CHIP (Title XXI-funded MA for infants 275-283% FPG and pregnant people;
  MinnesotaCare is a Basic Health Program). Taken 2: 2.2.2.1 MA-FCA Bases of Eligibility
  (published 2026-06-03) and 2.2.3.3 MA-FCA Income Limit (published 2018-12-01), RoboHelp topic
  body `#rh-topic` as blocks.
- **us-sc** (blocked) SCDHHS Medicaid Policy and Procedures Manual https://img1.scdhhs.gov/mppm/
  (Chapter 204 Healthy Connections Plans for Children is the CHIP chapter) and
  www1.scdhhs.gov/mppm/: after the chain repair described above both return HTTP 403 "Error Page"
  to plain and chrome120 clients; www.scdhhs.gov (CloudFront) returns 403 "The request could not
  be satisfied" for its policy index pages. 0 taken.

## Reviewer judgments

1. **Done-by-pointer to another branch's artifacts (NC, NJ, VA).** The pointers name scopes
   produced by the parallel Medicaid run; those manifests are not on this branch. If that run is
   not merged or its artifacts are cut differently, these three rows need revisiting.
2. **Pennsylvania granularity.** Chapter-level sections only: the publisher's subsection labels
   repeat (label 2.1 appears three times), so subsection labels would collide. The glossary
   (page 5) precedes the first chapter and is not captured. The CHIP Procedures Handbook and the
   state-hosted CHIP State Plan were left on the index.
3. **Maryland source.** regs.maryland.gov is a maryland.gov domain operated for the Division of
   State Documents by Open Law Library and is where dsd.maryland.gov redirects; it asks visitors
   to use its bulk GitHub downloads rather than scrape. 17 page fetches were made directly. The
   two repealed sections were taken (heading-only bodies). expression_date 2026-04-13 (latest
   amendment, .11D) is used for all 17 sections.
4. **Colorado title and headings.** The SOS lists 10 CCR 2505-3 as "Financial Management of the
   Children's Basic Health Plan" although it is the whole CHP+ rule; sections 210 and 510 have no
   title line, so their first sentence is the heading; 610's body is the editor's notes.
5. **Minnesota selection.** Two MA-FCA topics were taken as the CHIP-governing manual text;
   household composition and income methodology topics also apply. 2.2.3.3 carries a 2018
   publication date.
6. **Washington** takes HCA's manual chapter (WAC text plus clarifying information) under
   `manual`, not the WAC from app.leg.wa.gov under `regulation`.
7. **Tennessee** citation path `us-tn/regulation/1200-13/21/NN` mirrors the existing
   `us-tn/regulation/1240-01/02/01` shape.
8. **South Carolina certificate.** The GoDaddy G2 intermediate is committed although SC stayed
   blocked; it documents the repaired chain for the next attempt. A reviewer may drop it.
9. **Ohio and Wisconsin** blocks look transient (connect timeouts on hosts that served this
   corpus before); California, Arizona, Florida, Kansas, Louisiana and South Carolina are 403s.
10. **Serving overlap.** Every new `manual` and `regulation` scope shares its
    `(jurisdiction, document_class)` pair with existing scopes (e.g. us-md/regulation TCA COMAR,
    us-co/regulation CCR, us-tn/regulation SNAP rules); the controller must include both versions
    in a release's membership when activating.

Remaining (controller): `sign-ingest-manifest` per scope, immutable release selector,
`publish_corpus.py --dry-run` then publish (Supabase, R2). Not done here: push, sign, publish,
Supabase load.
