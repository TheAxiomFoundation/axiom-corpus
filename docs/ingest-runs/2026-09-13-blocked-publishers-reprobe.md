# Blocked publishers: re-probe of every `blocked_primary_source` queue row from a US network (2026-09-13)

Date: 2026-09-13. Branch: `discovery/blocked-publishers-reprobe` (sparse worktree on `origin/main`, corpus root
`/Users/pavelmakarchuk/axiom-corpus/data/corpus`). Probe pass 2026-09-13T19:57:21Z to 19:57:51Z (74 distinct URLs, 8 threads);
extraction 20:14Z (GA, TX) and 20:22Z (NE). GitNexus MCP tools were not available in this session; impact analysis was
done by reading the generators directly.

## Scope and protocol

Every row with `queue_status: blocked_primary_source` in the program agent queues on `origin/main` (`manifests/*-agent-queue.yaml`
plus `manifests/snap-completion-agent-queue.yaml`): 78 rows across CCDF (8), CHIP (10), LIHEAP (1), Medicaid (8), SNAP completion (6),
SSI (6), TANF (4) and WIC (35). The four `blocked_primary_source` rows of `manifests/state-statute-agent-queue.yaml` (AR, MS, MO, NH
statute adapters, May 2026, no `index_url`) belong to the statute-adapter queue, not to a program queue, and were not probed.

Per row: one plain HTTP GET of the recorded `index_url` with the extractor's own client (a `requests.Session` with the
`OFFICIAL_DOCUMENT_USER_AGENT`, Accept and Accept-Language headers of `extract_official_documents`; 20 s timeout; TLS verified
against certifi plus the committed intermediates in `data/certs/`). Where the recorded block sits on a different host than
`index_url` (the CCDF Lead Agency pages recorded in `publisher_index_url`, the OH eManuals host and the AZ WIC agencies page recorded
in `primary_source_url`), that URL was fetched once too. No impersonation profile, proxy, mirror or archived copy was used and
verification was never disabled. Bodies were classified as content or challenge by status, size and the challenge markers
(F5/TSPD, Incapsula, Cloudflare "Just a moment", AWS WAF, CAPTCHA, antibot forms, login redirects). Hosts that answered content
were read once more to inventory their document links. Script: `probe_blocked.py` (scratch, not committed; the table below is its
output).

## Results

78 rows probed. 3 cleared and extracted (CCDF GA, CCDF TX, Medicaid NE). 24 still blocked and recorded as durable (the same failure
from two networks on two dates). 8 WIC hosts answer but publish no manual (recorded as such; they were access blocks on 2026-09-10).
1 needs a decision (Medicaid AL: the host now completes TLS only with its missing GlobalSign intermediate and the recorded manual page
is gone). 36 publisher-posts-nothing rows and 6 not-applicable rows confirmed with today's probe.

| Queue | Row | 2026-09-10/11 result | 2026-09-13 plain probe (URL probed, status, bytes, seconds, body) | Outcome |
| --- | --- | --- | --- | --- |
| ccdf | us-as | TLS self-signed, expired cert (curl 60) | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; www.dhss.as/index.html: no response after 0.6 s (SSLError: HTTPSConnectionPool) | still blocked, durable |
| ccdf | us-az | 403 Cloudflare | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; des.az.gov/services/child-and-family/child-care/child-care-and-development-fund-state-plan: HTTP 403, 5,958 B, 0.1 s, challenge:cloudflare | still blocked, durable |
| ccdf | us-ga | connection reset / empty reply | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; www.decal.ga.gov/BftS/CCDFPlan.aspx: HTTP 200, 81,837 B, 0.7 s, content | cleared and extracted |
| ccdf | us-md | plan page 403 Cloudflare 'Access denied' | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; earlychildhood.marylandpublicschools.org/about/ccdf-state-plan: HTTP 200, 117,379 B, 0.5 s, content | still blocked, durable |
| ccdf | us-mo | 200 Drupal antibot form instead of PDF | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; dese.mo.gov/childhood/child-care-subsidy/child-care-dev-fund: HTTP 200, 81,955 B, 0.1 s, challenge:incapsula,antibot | still blocked, durable |
| ccdf | us-ny | 200 F5/TSPD challenge | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; ocfs.ny.gov/main/childcare/stateplan/: no response after 0.1 s (ConnectionError:) | still blocked, durable |
| ccdf | us-mp | 403 nginx | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; www.childcare.gov.mp/: HTTP 403, 358 B, 2.5 s, challenge:access-denied | still blocked, durable |
| ccdf | us-tx | 202 AWS WAF challenge (403 CloudFront earlier) | acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027: HTTP 202, 2,467 B, 0.3 s, challenge:aws-waf; www.twc.texas.gov/programs/child-care/data-reports-plans: HTTP 200, 122,911 B, 0.2 s, content | cleared and extracted |
| chip | us-as | no DNS record | medicaid.as.gov/: no response after 0.2 s (ConnectionError: HTTPSConnectionPool) | publisher posts nothing; confirmed |
| chip | us-ca | 200 Incapsula challenge iframe | www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx: HTTP 200, 212 B, 0.2 s, challenge:incapsula | still blocked, durable |
| chip | us-dc | 200, rule text only via ASP.NET postbacks | dcregs.dc.gov/Common/DCMR/RuleList.aspx?ChapterNum=29-95: HTTP 200, 58,700 B, 1.0 s, content | still blocked, durable |
| chip | us-fl | ahca 404; floridakidcare.org 200, no manual | www.floridakidcare.org/: HTTP 403, 5,669 B, 0.3 s, challenge:cloudflare; ahca.myflorida.com/medicaid/florida-kidcare: HTTP 404, 1,620 B, 0.1 s, not-found | still blocked, durable |
| chip | us-gu | 200, no document links | dphss.guam.gov/services/medicaremedicaid: HTTP 200, 93,777 B, 3.6 s, challenge:antibot,login | publisher posts nothing; confirmed |
| chip | us-mp | 200, no eligibility document | www.cnmimedicaid.org/departments/eligibility-enrollment: HTTP 200, 223,772 B, 0.3 s, content | publisher posts nothing; confirmed |
| chip | us-mt | 405 'Human Verification' CAPTCHA | rules.mt.gov/gateway/ChapterHome.asp?Chapter=37%2E79: HTTP 200, 894 B, 0.2 s, content | still blocked, durable |
| chip | us-pr | 200, provider files only | medicaid.pr.gov/CMS/5: HTTP 200, 195,309 B, 1.0 s, content | publisher posts nothing; confirmed |
| chip | us-vi | 200, forms and provider manual only | dhs.vi.gov/office-of-medicaid/: HTTP 200, 141,356 B, 3.0 s, content | publisher posts nothing; confirmed |
| chip | us-wy | 200, ASP.NET postbacks; member pages only | rules.wyo.gov/Search.aspx?mode=1&AgencyId=48: HTTP 200, 33,505 B, 0.5 s, content; health.wyo.gov/healthcarefin/chip/: HTTP 200, 218,761 B, 0.2 s, challenge:captcha | still blocked, durable |
| liheap | us-vi | index lists no VI plan; grantee posts ECAP forms only | liheapch.acf.gov/stateplans.htm: HTTP 200, 53,615 B, 0.5 s, content; dhs.vi.gov/family-assistance-programs/: HTTP 200, 137,037 B, 3.0 s, content | publisher posts nothing; confirmed |
| medicaid | us-al | TLS handshake never completes | medicaid.alabama.gov/content/9.0_Resources/9.4_Forms_Library/9.4.11_Eligibility_Manual.aspx: no response after 0.4 s (SSLError: HTTPSConnectionPool) | still blocked; index gone (decision needed) |
| medicaid | us-as | no DNS record | medicaid.as.gov/: no response after 0.2 s (ConnectionError: HTTPSConnectionPool) | publisher posts nothing; confirmed |
| medicaid | us-ca | 200 Incapsula challenge iframe | www.dhcs.ca.gov/services/medi-cal/eligibility/Pages/MEPM.aspx: HTTP 200, 212 B, 0.2 s, challenge:incapsula | still blocked, durable |
| medicaid | us-gu | 200, no document links | dphss.guam.gov/services/medicaremedicaid: HTTP 200, 93,777 B, 3.6 s, challenge:antibot,login | publisher posts nothing; confirmed |
| medicaid | us-mp | 200, no eligibility manual | www.cnmimedicaid.org/departments/eligibility-enrollment: HTTP 200, 223,772 B, 0.3 s, content | publisher posts nothing; confirmed |
| medicaid | us-ne | SOS API 403 Azure gateway; dhhs.ne.gov TCP timeout | dhhs.ne.gov/Pages/Title-477.aspx: HTTP 200, 194,402 B, 0.5 s, content; rules.nebraska.gov/api/chapter/GetByTitleId/232: HTTP 200, 686,881 B, 0.6 s, content | cleared and extracted |
| medicaid | us-pr | 200, provider files only | medicaid.pr.gov/CMS/5: HTTP 200, 195,309 B, 1.0 s, content | publisher posts nothing; confirmed |
| medicaid | us-vi | 200, forms and provider manual only | dhs.vi.gov/office-of-medicaid/: HTTP 200, 141,356 B, 3.0 s, content | publisher posts nothing; confirmed |
| snap-completion | us-as | dhss.as placeholders; TLS self-signed | fns-prod.azureedge.us/nap/nutrition-assistance-program-block-grants: HTTP 200, 53,561 B, 0.8 s, content; dhss.as/index.html: HTTP 200, 12,095 B, 1.0 s, content | publisher posts nothing; confirmed |
| snap-completion | us-az | 403 F5/TSPD challenge | dbmefaapolicy.azdes.gov/FAA5.html: HTTP 200, 115,281 B, 0.5 s, content | still blocked, durable |
| snap-completion | us-gu | 200, no manual or plan | dphss.guam.gov/bureau-economic-security-bes: HTTP 200, 106,725 B, 3.7 s, challenge:antibot,login | publisher posts nothing; confirmed |
| snap-completion | us-ny | connection reset / TSPD challenge | otda.ny.gov/programs/snap/: no response after 0.2 s (ConnectionError:) | still blocked, durable |
| snap-completion | us-oh | eManuals TCP connect timeout | codes.ohio.gov/ohio-administrative-code/5101%3A4: HTTP 200, 14,653 B, 0.3 s, content; emanuals.jfs.ohio.gov/FoodAssistance/: no response after 20.1 s (ConnectTimeout: HTTPSConnectionPool) | still blocked, durable |
| snap-completion | us-vi | 200, no manual or plan | dhs.vi.gov/family-assistance-programs/: HTTP 200, 137,037 B, 3.0 s, content | publisher posts nothing; confirmed |
| ssi | us-as | not applicable (42 U.S.C. 1382c(e)) | secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05005: HTTP 200, 48,992 B, 0.3 s, content; uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section1382c&num=0&edition=prelim: HTTP 200, 228,944 B, 4.5 s, content | not applicable (program absent); confirmed |
| ssi | us-gu | not applicable | secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05005: HTTP 200, 48,992 B, 0.3 s, content; uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section1382c&num=0&edition=prelim: HTTP 200, 228,944 B, 4.5 s, content | not applicable (program absent); confirmed |
| ssi | us-ny | connection reset / TSPD challenge | otda.ny.gov/programs/ssp/: no response after 0.1 s (ConnectionError:) | still blocked, durable |
| ssi | us-pr | not applicable | secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05005: HTTP 200, 48,992 B, 0.3 s, content; uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section1382c&num=0&edition=prelim: HTTP 200, 228,944 B, 4.5 s, content | not applicable (program absent); confirmed |
| ssi | us-vi | not applicable | secure.ssa.gov/apps10/poms.nsf/subchapterlist!openview&restricttocategory=05005: HTTP 200, 48,992 B, 0.3 s, content; uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section1382c&num=0&edition=prelim: HTTP 200, 228,944 B, 4.5 s, content | not applicable (program absent); confirmed |
| ssi | us-wy | 200, script-rendered Drive embed | ecom.wyo.gov/: HTTP 200, 218,582 B, 0.3 s, content | still blocked, durable |
| tanf | us-as | not applicable (no TANF program) | dhss.as/index.html: HTTP 200, 12,095 B, 1.0 s, content; uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section619&num=0&edition=prelim: HTTP 200, 146,988 B, 10.1 s, content | not applicable (program absent); confirmed |
| tanf | us-mp | not applicable (42 U.S.C. 619(5)) | uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title42-section619&num=0&edition=prelim: HTTP 200, 146,988 B, 10.1 s, content | not applicable (program absent); confirmed |
| tanf | us-ny | connection reset / TSPD challenge | otda.ny.gov/programs/temporary-assistance/: no response after 0.1 s (ConnectionError:) | still blocked, durable |
| tanf | us-vi | 200, no manual, rule or plan | dhs.vi.gov/family-assistance-programs/: HTTP 200, 137,037 B, 3.0 s, content | publisher posts nothing; confirmed |
| wic | us-ak | see queue note | health.alaska.gov/en/services/division-of-public-assistance-dpa-services/wic/: HTTP 200, 140,494 B, 1.4 s, content | publisher posts nothing; confirmed |
| wic | us-al | see queue note | www.alabamapublichealth.gov/wic/index.html: HTTP 200, 59,815 B, 0.4 s, content | publisher posts nothing; confirmed |
| wic | us-ar | 403 Cloudflare | healthy.arkansas.gov/programs-services/community-family-child-health/wic-women-infants-children/: HTTP 200, 293,905 B, 0.2 s, content | still blocked; host answers, no manual published |
| wic | us-as | see queue note | aswic.com/: HTTP 200, 62,987 B, 0.8 s, challenge:captcha | publisher posts nothing; confirmed |
| wic | us-az | 200 soft 404 / missing #manuals anchor | www.azdhs.gov/prevention/azwic/local-agencies/index.php: HTTP 200, 70,489 B, 0.7 s, content | still blocked; host answers, no manual published |
| wic | us-de | 403 'Web App - Unavailable' | www.dhss.delaware.gov/dhss/dph/chs/wichome.html: HTTP 403, 1,892 B, 0.2 s, challenge:access-denied | still blocked, durable |
| wic | us-fl | see queue note | www.floridahealth.gov/individual-family-health/womens-health/wic/: HTTP 200, 222,622 B, 0.2 s, content | publisher posts nothing; confirmed |
| wic | us-gu | see queue note | dphss.guam.gov/dphss-programs/women-infants-children-wic-program: HTTP 200, 95,080 B, 3.6 s, challenge:antibot,login | publisher posts nothing; confirmed |
| wic | us-hi | see queue note | health.hawaii.gov/wic/wic-la-information/: HTTP 200, 60,954 B, 0.6 s, content | publisher posts nothing; confirmed |
| wic | us-id | see queue note | healthandwelfare.idaho.gov/services-programs/food-assistance/about-wic: HTTP 200, 180,829 B, 0.5 s, content | publisher posts nothing; confirmed |
| wic | us-il | DNS failure (page-not-found earlier) | www.dhs.state.il.us/page.aspx?item=36418: HTTP 200, 7,619 B, 0.2 s, content | still blocked; host answers, no manual published |
| wic | us-in | see queue note | www.in.gov/health/wic/wic-staff: HTTP 200, 52,040 B, 0.4 s, content | publisher posts nothing; confirmed |
| wic | us-ks | 200, empty Document Center shell | www.kdhe.ks.gov/1149/Information-for-WIC-Local-Agencies: HTTP 200, 122,556 B, 0.7 s, content | still blocked; host answers, no manual published |
| wic | us-la | 200, no manual link | ldh.la.gov/bureau-of-nutrition-services/women-infants-children-program: HTTP 403, 479 B, 0.5 s, challenge:cloudflare,access-denied | still blocked, durable |
| wic | us-ma | 403 | www.mass.gov/orgs/women-infants-children-nutrition-program: HTTP 200, 308,139 B, 0.1 s, content | still blocked; host answers, no manual published |
| wic | us-mo | redirect to portal login | health.mo.gov/providers/manuals/wic-operations-manual-wom/: HTTP 200, 90,487 B, 0.6 s, login-redirect | still blocked, durable |
| wic | us-mp | see queue note | www.chcc.health/cnmi-wic.php: HTTP 200, 45,278 B, 0.2 s, content | publisher posts nothing; confirmed |
| wic | us-ms | see queue note | msdh.ms.gov/page/41,0,128,1081.html: HTTP 200, 37,588 B, 0.3 s, content | publisher posts nothing; confirmed |
| wic | us-mt | see queue note | dphhs.mt.gov/ecfsd/wic/wicstateplan: HTTP 200, 49,490 B, 0.4 s, content | publisher posts nothing; confirmed |
| wic | us-nd | see queue note | www.hhs.nd.gov/food-programs/WIC: HTTP 200, 452,860 B, 1.1 s, challenge:antibot,login | publisher posts nothing; confirmed |
| wic | us-ne | see queue note | dhhs.ne.gov/Pages/WIC-Policies-and-Procedures.aspx: HTTP 200, 282,671 B, 0.9 s, content | publisher posts nothing; confirmed |
| wic | us-nh | 403 'Access Denied' | www.dhhs.nh.gov/programs-services/health-care/nutrition-services/wic: HTTP 403, 447 B, 0.1 s, challenge:access-denied | still blocked, durable |
| wic | us-nm | intranet links only | www.nmwic.org/nm-wic-staff/policy-procedures/: HTTP 200, 232,386 B, 1.3 s, content | still blocked; host answers, no manual published |
| wic | us-nv | password-protected page | nevadawic.org/staff/policy-and-procedures/: HTTP 200, 60,492 B, 1.6 s, challenge:captcha,login | still blocked, durable |
| wic | us-ny | 200, no manual link | www.health.ny.gov/prevention/nutrition/wic/: HTTP 403, 919 B, 0.2 s, blocked:403 | still blocked, durable |
| wic | us-oh | 404 | odh.ohio.gov/know-our-programs/Women-Infants-Children/Local-Staff: HTTP 404, 5,285 B, 0.4 s, not-found | still blocked; host answers, no manual published |
| wic | us-ok | see queue note | oklahoma.gov/health/services/children-family-health/wic.html: HTTP 200, 576,476 B, 0.1 s, content | publisher posts nothing; confirmed |
| wic | us-pr | see queue note | wic.pr.gov/: HTTP 200, 5,894 B, 0.5 s, content | publisher posts nothing; confirmed |
| wic | us-sc | see queue note | dph.sc.gov/health-wellness/family-planning/women-infants-and-children-wic-nutrition-program: HTTP 200, 384,361 B, 0.2 s, content | publisher posts nothing; confirmed |
| wic | us-sd | see queue note | doh.sd.gov/programs/wic/: HTTP 200, 87,299 B, 0.6 s, content | publisher posts nothing; confirmed |
| wic | us-tn | 404 (relocated page has no manual index) | www.tn.gov/health/health-program-areas/fhw/wic.html: HTTP 404, 68,643 B, 1.3 s, not-found | still blocked; host answers, no manual published |
| wic | us-vi | see queue note | doh.vi.gov/programs/women-infants-and-children/more-wic-information/: HTTP 200, 177,707 B, 3.6 s, content | publisher posts nothing; confirmed |
| wic | us-vt | see queue note | www.healthvermont.gov/family/wic: HTTP 200, 297,025 B, 0.3 s, challenge:antibot | publisher posts nothing; confirmed |
| wic | us-wi | see queue note | www.dhs.wisconsin.gov/wic/professionals.htm: HTTP 200, 166,465 B, 0.2 s, content | publisher posts nothing; confirmed |
| wic | us-wy | see queue note | health.wyo.gov/publichealth/wic/: HTTP 200, 190,896 B, 0.8 s, challenge:captcha | publisher posts nothing; confirmed |

Note on the ACF CCDF index itself: `acf.gov/occ/form/approved-ccdf-plans-fy-2025-2027` now answers the plain extractor client with
HTTP 202 and a 2,467-byte AWS WAF challenge body; the CCDF generator's browser User-Agent still receives the directory (HTTP 200,
84,254 bytes). The Lead Agency pages, not the directory, were the recorded blocks, so this did not affect the pass.

## Cleared rows and what was extracted

All three scopes were written into `/Users/pavelmakarchuk/axiom-corpus/data/corpus` (unsigned, uncommitted; `data/` is gitignored)
with `REQUESTS_CA_BUNDLE` = certifi plus the committed `data/certs/*.pem` intermediates.

| Scope | Manifest | Documents | Provisions | Coverage | Bodies |
| --- | --- | ---: | ---: | --- | --- |
| `us-ga/policy/2026-09-13-ccdf-plan-fy2025-2027` | `manifests/us-ga-ccdf-state-plan-fy2025-2027.yaml` | 1 (CCDF Plan FFY 2025-2027, Amendment 2, approved 2026-02-13, 388 pages) | 42 (root + 41 preprint sections 1.1-10.2) | complete | all 41 sections non-empty (min 2,342 chars) |
| `us-tx/policy/2026-09-13-ccdf-plan-fy2025-2027` | `manifests/us-tx-ccdf-state-plan-fy2025-2027.yaml` | 1 (CCDF Plan FFY 2025-2027, Amendment 1, approved 2026-07-01, 216 pages) | 42 (root + 41 sections) | complete | all 41 sections non-empty (min 2,624 chars) |
| `us-ne/regulation/2026-09-13-medicaid-state-eligibility-manual` | `manifests/us-ne-medicaid-eligibility-manual.yaml` | 68 (28 Title 477 NAC chapter PDFs from the Secretary of State API, chapter 19 excluded because the CHIP scope already carries `us-ne/regulation/title-477/chapter-19`; 40 Title 477 appendix PDFs from the DHHS appendix page) | 998 (68 roots, 790 labeled sections, 139 appendix pages, 1 single body) | complete | every section and page row carries text except 46 heading-only parent sections (e.g. `chapter-3/005 APPLICATION.`, whose text is in its 005.01-005.06 children) |

**CCDF GA and TX.** `scripts/build_ccdf_state_plan_manifests.py` now carries the two resolutions as `agent_ready` with a per-state
`scope_version` / `source_as_of` (2026-09-13) so the 2026-09-10 scopes are untouched; `--only ga,tx,...` writes the manifest from the
ACF index facts the row already holds (`ready_row_fields`, factored out of the full run). Both PDFs are Aspose CARS prints; the
shared `CARS_EXTRACTION` matched 41/41 preprint labels with no repeats. TX's page links the ACF-hosted Appendix separately (not taken).
Neither citation path (`us-xx/policy/acf/ccdf-plan/fy2025-2027`) existed anywhere under `data/corpus/provisions/us-ga` or `us-tx`.

**Medicaid NE.** `scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 7` adds `build_ne`: the chapter listing from
`rules.nebraska.gov/api/chapter/GetByTitleId/232` (29 chapters), chapter PDFs from the file API (the plain `pdfBlobName`; chapter 25's
signed `_Official` blob answers HTTP 400), and the 40 `477-000-NNN` appendix PDFs linked from `dhhs.ne.gov/Pages/Title-477-Appendix.aspx`.
Two heading patterns: the CHIP chapter-19 pattern for 2020+ filings (`001. SCOPE AND AUTHORITY.`) and an older-numbering pattern for
the 2018 filings (`16-001.01A Heading: body`); chapter 14 is an unnumbered definitions list and is one body. Appendices are page-level
(`page_citation_prefix: page`). `document_class: regulation` (the CHIP precedent for 477 NAC). Follow-on for the CHIP owner: the
2026-09-10 CHIP row's 477 NAC 19 (effective 2020-07-29) is unchanged on the API listing.

**Draft selector.** `docs/ingest-runs/2026-09-13-us-rulespec-followup-union.selector.json` (read from the main checkout, 556 scopes) plus
the three scopes above, validated from the worktree with
`axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus --release <draft> --ignore-r2-missing --max-issues 50`:
`ok: true`, `error_count: 0`, 559 scopes, 546 pre-existing `missing_parent_id` warnings (us-ca MPP recovery scope), no cross-scope
citation-path collision. The draft stayed in the scratch directory.

## Still blocked: what changed and what did not

- **AZ SNAP (FAA5).** The host now lets the first plain requests of a session through: the index answered HTTP 200 with the real
  WebWorks table of contents (80 section pages; 24 already have citation paths in the two released us-az FAA5 scopes, 56 do not,
  including two pages added since the 2025-10-30 manifest: FFY 2027 NA COLA Changes and Electronic Benefit Transfer (EBT) Screens;
  FFY 2026 NA COLA Changes is gone) and one section page answered 200 (6,511 bytes). From the third request on, Cloudflare answered
  HTTP 403 with a 5,811-byte "Just a moment..." challenge (`Cf-Mitigated: challenge`), including the official-documents extractor's own
  fetch of the first completion page (20:03Z) and a re-check (20:06Z). No completion scope was built; the challenge was not worked
  around. Recorded as a durable bot challenge (F5/TSPD on 09-10/11, Cloudflare on 09-13). The 56-page gap list is
  `az_faa5_pages.json` in the scratch directory and can be rebuilt from the TOC in one request.
- **AL Medicaid.** `medicaid.alabama.gov` now completes the handshake but serves only its leaf certificate (issuer GlobalSign Atlas
  R3 OV TLS CA 2026 Q1, valid 2026-04-06 to 2026-10-22). With the chain completed from the leaf's AIA URL (the public intermediate,
  kept in scratch and not committed because nothing was extracted) the host answers, but the recorded Eligibility Manual page
  (`9.4.11_Eligibility_Manual.aspx`) is HTTP 404 and the Forms Library now numbers 9.4.11 as Mental Health Forms; the Forms Library,
  Provider Manuals and Apply pages link no eligibility manual. Left `blocked_primary_source` with the finding; a reviewer needs to
  decide where (or whether) Alabama Medicaid now publishes the manual before the intermediate is added to `data/certs/`.
- **CCDF MO** landing page 200, but every plan media path (initial plan, Amendment #2) still returns the Drupal antibot form instead of
  a PDF. **CCDF MD** landing 200, plan page 403 Cloudflare "Access denied". **CCDF AZ** 403 Cloudflare; **NY** (all four OTDA/OCFS
  rows) connection reset; **MP** 403 nginx; **AS** self-signed expired certificate.
- **CHIP MT**: the 2026-09-10 CAPTCHA is gone but `rules.mt.gov` answers only the 894-byte "Montana SOS" application shell; no rule
  text is fetchable. **CHIP/Medicaid CA**: 212-byte Incapsula challenge. **CHIP FL**: floridakidcare.org now 403 Cloudflare (it had no
  manual when it answered on 09-10), ahca 404. **CHIP DC, WY** and **SSI WY**: publisher structures (ASP.NET postbacks, a Google
  Sites Drive embed) unchanged; not network blocks, recorded as not fetchable on two dates.
- **SNAP OH** eManuals host: ConnectTimeout after 20.1 s (codes.ohio.gov 200; OAC 5101:4 complete in the corpus).
- **WIC access blocks.** DE (403 'Web App - Unavailable') and NH (403 'Access Denied') unchanged. LA has gone back to 403 Cloudflare
  (its page listed no manual on 09-10). NY's health.ny.gov now answers 403 CloudFront to the plain client (no manual on 09-10). AR and MA
  now answer 200 but list no manual (AR: only the FY27 income guidelines PDF across the WIC sub-pages; MA: the org page links no manual,
  matching the state plan's own description); IL resolves again and the manual page is still "Page Not Found"; KS still hides the
  manual behind the CivicEngage Document Center shell (the admin endpoint that challenged on 09-10 was not requested again); AZ still
  serves the soft 404 and the missing `#manuals` anchor; MO still redirects to the portal login; NV still password-protected; NM still
  intranet links only; TN and OH still 404.

Every still-blocked row's note now ends with the 2026-09-13 probe (stamp, status, bytes, seconds, body) and the sentence that the
block is durable across two networks and two dates, so the dashboard can treat the cell as not available rather than pending.
Publisher-posts-nothing rows (the 16 WIC states plus the five WIC territories, the territory rows of Medicaid, CHIP, SNAP, TANF
and LIHEAP) keep their status and gain the confirmation; the 6 not-applicable rows (SSI PR/GU/VI/AS, TANF AS/MP) likewise.

## Queue changes (all through the generators)

| Generator | Invocation | Rows changed |
| --- | --- | --- |
| `scripts/build_ccdf_state_plan_manifests.py` | `--only ga,tx,as,az,md,mo,ny,mp` | GA, TX → `agent_ready` (2026-09-13 scope); AS, AZ, MD, MO, NY, MP notes |
| `scripts/build_medicaid_state_eligibility_manual_manifests.py` | `--batch 7` | NE → `agent_ready`; AL, CA, AS, GU, MP, PR, VI notes |
| `scripts/build_snap_state_manual_completion_manifests.py` | `--static-only` | AZ, NY, OH, AS, GU, VI notes (`REPROBE_NOTES`) |
| `scripts/build_wic_manifests.py` | `--only <35 blocked rows>` | 35 notes (`REPROBED_2026_09_13`) |
| `scripts/build_chip_state_eligibility_manifests.py` | (full static run) | CA, MT, FL, DC, WY, AS, GU, MP, PR, VI notes |
| `scripts/build_ssi_state_supplement_manifests.py` | `--batch 5` | NY, WY, PR, GU, VI, AS notes |
| `scripts/build_tanf_state_policy_manual_manifests.py` | `--only us-ny --only us-vi --only us-as --only us-mp` | NY, VI, AS, MP notes |
| `scripts/build_liheap_state_plan_manifests.py` | `--territories --only us-vi` | VI note |

Status counts after the pass: CCDF agent_ready 47 / blocked 6 / needs_review 6; Medicaid agent_ready 43 / blocked 7 / done 6 /
needs_review 2; the other queues' counts are unchanged. Every queue diff was checked row by row: only the rows above changed. The CHIP
full run also regenerated `manifests/us-nh-chip-state-eligibility-manual.yaml` from its static table (the committed manifest carries a
hand edit, `section_label_template: '{part}.{section}'`, that the generator's `NH_HE_W_EXTRACTION` does not); that change was
reverted and is noted here for the CHIP owner.

## Checks

- `uv run ruff check scripts`: clean.
- Focused pytest in the sparse worktree (`-m "not integration and not slow" -k "manifest or official_documents or discovery"`):
  286 passed, 2 skipped, 12 failed. The failures open other scopes' `data/corpus` artifacts that the sparse worktree does not hold:
  the ten known ones (BE rulespec promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI/MT/ND/NY SNAP manual TOC tests)
  plus `test_armenia_arlis.py::test_checked_in_tax_code_2024_continuity_sources_match_manifest` and
  `test_israel_openlaw.py::test_pilot_manifest_pins_all_three_instruments`, which read retained source artifacts the same way.
- Disk: 16 GB free at the start; another process brought it to 4.6 GB during the pass; every extraction was preceded by a check
  against the 3 GB floor (lowest seen 4.6 GB).

## Decisions needed

1. **Medicaid AL**: where Alabama Medicaid now publishes its Eligibility Manual (the recorded index is gone; the host needs the
   GlobalSign Atlas R3 OV intermediate in `data/certs/` before any extraction).
2. **SNAP AZ**: the FAA5 host passes the first plain requests of a session and challenges the rest; 56 of 80 pages are missing from the
   corpus. Whether a request-paced completion run is acceptable is a reviewer call; nothing was attempted here.
3. **CHIP NH manifest**: the committed manifest and the generator's static table disagree on `section_label_template`; reconcile in
   the CHIP generator so a full run stops reverting the hand fix.
4. The three new scopes are unsigned and on disk only; they belong in the next follow-up selector cut.
