# SNAP state policy manuals, completion batch 1 (axiom-corpus#680)

Date: 2026-09-10
Program: SNAP (`manifests/state-snap-manual-agent-queue.yaml`, 51 rows, unchanged; this pass is
tracked in the new `manifests/snap-completion-agent-queue.yaml`)
Issue: https://github.com/TheAxiomFoundation/axiom-corpus/issues/680 ("SNAP discovery missed
~24 states")
Agent: two sessions. The first ran roughly 2026-09-10T19:40Z to 20:40Z (diagnosis, index
inventories, generator, TX and NH manifests and extraction; it was killed before the run note and
commit). The continuation started_at 2026-09-10T20:42:54Z, finished_at 2026-09-10T20:51:08Z, wall time
8m 14s; it verified the on-disk state against the manifests and the corpus, wrote this note,
ran ruff and the tests and committed. No manifest, queue row or artifact changed in the
continuation.
Impact analysis: not run; the GitNexus MCP tools were unavailable in both sessions. No existing
function was modified: the only code added is
`scripts/build_snap_state_manual_completion_manifests.py`.

## Selection rule (reviewer judgment)

Batch 1 = the four ingestion-gap states named in #680 (FL, AL, MD, MA: more documents registered
than "captured") followed by the six discovery-gap states TX, CA, NY (the three largest by
population) and NH, KY, ME (the three thinnest, 1-2 "captured"). Attempted: 10. Extracted: TX, NH
(2). Diagnosed, nothing failed to land: FL, AL, MD, MA (4). Index confirmed complete, nothing to
take: CA, ME (2). Blocked publisher: KY, NY (2).

Released SNAP scopes are immutable, so every document missing from the corpus goes into a new
scope per state: version `2026-09-10-snap-state-manual-completion`, `document_class` per the
state's existing convention, manifest `manifests/us-xx-snap-manual-completion.yaml`, citation
paths under the state's existing convention. A release rejects duplicate citation paths across
scopes, so every candidate citation path was checked against every provisions JSONL under
`/Users/pavelmakarchuk/axiom-corpus/data/corpus/provisions/<jurisdiction>/` (all document classes,
all versions) before it was taken; the generator skips and records collisions
(`citation_path_already_in_corpus`). None occurred for TX or NH.

Every document was confirmed on the publisher's own index, fetched live. No mirrors, archives,
compiled lists or PolicyEngine files were used as sources. TLS verification was never disabled and
no publisher needed a certificate bundle (no `data/certs` change). No new adapter: extraction is
`uv run axiom-corpus-ingest extract-official-documents`.

## Diagnosis of the four ingestion-gap states

#680 computes "registered" from manifests whose program tag is SNAP and "captured" as encoding-queue
items plus rulespec artifacts. Comparing each manifest's document list with the released scope's
inventory and coverage in `data/corpus` shows that in all four states every registered document
landed; the gap is between "ingested" and "queued/encoded" (the dashboard's `stalled_registered`
bucket), not an extraction, scope-cut or selector failure. No completion scope is needed for any of
the four.

**us-fl** (68 registered, 48 captured). The 68 are `manifests/us-fl-snap-primary-policy.yaml`,
FAC 65A-1 sections republished by Cornell LII (`primary_source: false`); all 68 roots are present in
the released scope `us-fl/regulation/2026-05-29-r2026-07-15-self-contained` (204 provisions,
coverage complete). The 48 are the DCF ESS Program Policy Manual PDFs
(`manifests/us-fl-ess-manual.yaml`, program tag ESS, so not counted as SNAP-registered); all 48 roots
are present in `us-fl/manual/2026-05-27-fl-ess-manual-r2026-07-15-self-contained` (1,107
provisions, coverage complete). The publisher index
(https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual)
lists 76 PDFs today: the same 48 manual sections plus 28 quarterly Summary of Changes PDFs (a
change-summary family, not taken).

**us-al** (59 registered, 17 captured). 59 = 42 Ala. Admin. Code 660-4 sections republished by
Cornell LII (`manifests/us-al-snap-primary-policy.yaml`, `primary_source: false`; all 42 roots in
`us-al/regulation/2026-05-29-r2026-07-15-self-contained`, 126 provisions) + the 17 DHR POE Online
Manual chapter PDFs (`manifests/us-al-snap-manual.yaml`; all 17 roots in
`us-al/manual/2026-05-27-al-snap-poe-manual-r2026-07-15-self-contained`, 149 provisions, coverage
complete). Captured 17 = the POE chapters in the encoding queue. Publisher index re-check today
was not possible: apps.dhr.alabama.gov TCP connect timeout (curl 28 after 30 s plain request;
curl-cffi chrome120 the same after 20 s); the 17-chapter inventory stands from the 2026-05-27 row.

**us-md** (54 registered, 53 captured). 54 = 51 manual files (`manifests/us-md-fsp-manual.yaml`;
all 51 roots in `us-md/manual/2026-07-17-md-snap-manual`, 379 provisions, coverage complete) + 3
FIA FY2026 guidance documents (`manifests/us-md-fia-snap-fy2026-guidance.yaml`, released scope
`us-md/guidance/2026-07-12-md-fia-snap-fy2026`). Captured 53 = 51 queue items + 2 artifacts; the
one-document gap is a guidance row with no queue item or artifact. The publisher index
(https://dhs.maryland.gov/supplemental-nutrition-assistance-program/food-supplement-program-manual/)
lists exactly the same 51 files today.

**us-ma** (54 registered, 12 captured). 54 = 44 106 CMR 364-365 sections republished by Cornell
LII (`manifests/us-ma-snap-primary-policy.yaml`, `primary_source: false`) + 9 official DTA chapter
files (343, 360-367; `manifests/us-ma-dta-snap-regulations.yaml`) + 1 COLA guidance document. 53 of
the 54 registered citation paths are present in the released consolidated scope
`us-ma/regulation/2026-07-21-ma-dta-regulations-consolidated` (332 provisions; all 9 chapter roots
present). The one absent path, `us-ma/regulation/106-cmr/364/360`, is a Cornell LII manifest entry
for a section number the official chapter 364 PDF does not carry, so it is not a missing official
document. Publisher index (https://www.mass.gov/lists/department-of-transitional-assistance-regulations):
the same 9 chapter PDFs plus a DOCX copy of each (same text, other format; not taken). The DTA
Online Guide named in #680 is a separate manual family whose index page carries only in-page
anchors and DTA Connect links; it is not an ingestion gap and is left for a discovery batch.

## Per-jurisdiction results

| Jurisdiction | Index | Found | Taken | Provisions | Extraction seconds | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| us-fl | DCF ESS Program Policy Manual | 76 | 0 | - | - | done (diagnosed) |
| us-al | DHR POE Online Manual | 17 (2026-05-27 row) | 0 | - | - | done (diagnosed; index host unreachable today) |
| us-md | DHS Food Supplement Program Manual | 51 | 0 | - | - | done (diagnosed) |
| us-ma | DTA regulations list | 18 | 0 | - | - | done (diagnosed) |
| us-tx | HHSC Texas Works Handbook | 507 | 283 | 4,392 | 12 | agent_ready (extracted) |
| us-ca | CDSS CalFresh Regulations (MPP Div. 63) | 15 | 0 | - | - | done (index complete) |
| us-ny | OTDA SNAP program page | - | 0 | - | - | blocked_primary_source |
| us-nh | DHHS Food Stamp Manual (WebHelp) | 1,542 | 502 | 1,006 | 678 | agent_ready (extracted) |
| us-ky | CHFS DCBS Division of Family Support | - | 0 | - | - | blocked_primary_source |
| us-me | SoS DHHS agency rules index | 3 | 0 | - | - | done (index complete) |

Total: 785 documents, 5,398 provisions across 2 new scopes. Extraction seconds are derived from
the artifact timestamps (first source file written to last coverage file written) because the first
session's timing log was lost with the session: TX 2026-09-10T19:41:27Z-19:41:39Z, NH
19:42:50Z-19:54:08Z. Found/taken per family are in the queue rows (`index_document_count`,
`taken_count`, `index_families`).

Coverage for both extracted scopes is `complete: true` with 0 missing, 0 extra and 0 duplicate
citation paths (`duplicate_provision_citations` and `duplicate_source_citations` empty).
Verified independently on the JSONL in the continuation: TX 4,392 rows, 4,392 distinct
`citation_path`; NH 1,006 rows, 1,006 distinct; all 283 / 502 manifest citation paths present as
roots; 0 collisions against every other provisions JSONL under `provisions/us-tx/` (seven files) and
`provisions/us-nh/` (one file); every inventory item names a regular, non-symlink file under
`sources/<jur>/manual/2026-09-10-snap-state-manual-completion/` whose SHA-256 matches (0 bad
references); 0 NH source files under 3 KB (no bot-challenge or error pages retained).

### Index inventories

**us-tx** — https://fhb.hhs.texas.gov/handbooks/texas-works-handbook (the publisher's handbook
host; www.hhs.texas.gov/handbooks/texas-works-handbook redirects there). Existing TX SNAP
convention: `manifests/us-tx-manuals.yaml`, `document_class: manual`, citation paths
`us-tx/manual/hhs/texas-works-handbook/<section-slug>`; the completion scope follows it.
The handbook has 10 parts. Parts A (Determining Eligibility), B (Case Management) and C (Appendix)
govern SNAP alongside TANF and Medicaid and are taken with the TWH Glossary; Parts D, E, F, M, R, W
and X are medical-program-only parts (CHIP, Medicaid for the elderly and disabled, former foster
care, MBCC, refugee medical assistance, Healthy Texas Women, MBI) and are inventoried, not taken.
Pages carry policy text (`article.c-article div.c-field--name-body`), only a "Pages in this
section" sub-menu (`.c-view--hb-submenus`), or both; menu-only pages are landing pages.
Families (507 found, 283 taken): part landing pages 10/0; Part A section pages 147/147; Part A
section landing pages 26/0; sections already in the released scopes 11/0 (`us-tx-manuals.yaml`:
A-220, A-1210, A-1220, A-1320, A-1340, A-1350, A-1420, A-2410, A-2420, C-110, D-1820;
`us-tx-twh-c120-snap-deduction-amounts.yaml`: C-120; the D-1820 path is outside the taken parts);
Part B section pages 88/88; Part B section landing pages 15/0; Part C section pages 47/47; Part C
section landing pages 15/0; Part D chapter pages 23/0; E 24/0; F 24/0; M 24/0; R 0/0; W 24/0;
X 23/0; glossary 1/1; forms, documents, notices, revisions, bulletins and contact pages 5/0.
Extraction selector `article.c-article div.c-field--name-body` with `.c-field__label` dropped, the
same shape as today's Medicaid TX scope: 283 documents, 4,392 provisions (283 roots + 4,109 HTML
blocks), 12 s.

**us-nh** — https://www.dhhs.nh.gov/fsm_htm/newfsm.htm ("Food Stamp/SNAP Policy Manual", linked
from the DHHS SNAP program page
https://www.dhhs.nh.gov/programs-services/food-meals-assistance/supplemental-nutrition-assistance-program-snap).
The released NH SNAP scope is the He-W 700 rules (`manifests/us-nh-snap-rules.yaml`,
`document_class: regulation`, `us-nh/regulation/he-w-700`); the Food Stamp Manual is a policy manual,
so the completion scope uses `document_class: manual` and the NH manual convention already used by
today's TANF scope (`us-nh/manual/dhhs/fam/<topic>`): `us-nh/manual/dhhs/fsm/<topic-slug>`. The
manual is RoboHelp WebHelp; topics were enumerated from the plain-HTML table of contents
(`whgdata/whlstt0.htm` ... `whlstt69.htm`, the next file answers 404), de-duplicated by topic file
(the TOC lists a topic under several books), and every topic was fetched once to confirm it answers
HTTP 200 and to inventory the Service Release documents it cites. The host answers HTTP 403 to the
plain Axiom request and 200 to the existing manifest option `request: browser_impersonation: true`
(curl-cffi chrome120), exactly as the NH Family Assistance Manual scope does; the manifest carries
that option. Families (1,542 found, 502 taken): WebHelp TOC pages 70/0; TOC links 861/0 (link
entries, collapsed to 502 distinct topics); Food Stamp Manual topic pages 502/502; unreachable
topics 0/0; Service Release (SR) documents cited by the topics (`sr_htm/html/sr_*.htm`) 109/0, a
separate document family. Extraction drops `#header`, `.no-print` and `.navBtnCusStyle`: 502
documents, 1,006 provisions (502 roots + 504 blocks; a WebHelp topic is one text block), 678 s
through the impersonation path.

**us-ca** — https://www.cdss.ca.gov/inforesources/letters-regulations/legislation-and-regulations/calworks-calfresh-regulations/calfresh-regulations
(the publisher's own index of MPP Division 63). 15 Food Stamp Manual files (fsman01-fsman12 incl.
04a/04b and 11a/11b/11c): 15 found, 0 taken, 15 already in
`manifests/us-ca-cdss-mpp-calfresh-complete.yaml` and the released scope
`us-ca/regulation/2026-07-17-ca-cdss-mpp-calfresh` (436 provisions, coverage complete). CDSS
publishes no separate CalFresh handbook; county handbooks are not state primary sources. #680's 18
"captured" = 15 queue items + 3 artifacts, a document count, not a section count.

**us-me** — https://www.maine.gov/sos/rulemaking/agency-rules/department-health-and-human-services-rules
10-144 Ch. 301 SNAP Rules (`144c301-2026-133-NSC.docx`, the same file as the released scope) and
Ch. 609 SNAP Employment and Training: 2 found, 0 taken, 2 already in `manifests/us-me-snap-rules.yaml`
and `us-me/regulation/2026-07-17-me-snap-rules` (223 provisions). Ch. 302 SUN Bucks (Summer EBT,
outside SNAP): 1 found, 0 taken. #680's 2 "captured" is a document count (two rulebooks).

### Blocked publishers (no workaround attempted)

**us-ky** — https://www.chfs.ky.gov/agencies/dcbs/dfs/Pages/default.aspx (the DCBS Division of
Family Support page that lists the Operation Manual volumes): HTTP 403 (1,484-byte error page) to
the plain Axiom request and the same HTTP 403 to curl-cffi chrome120 browser impersonation (20 s
timeout). The released scope `us-ky/manual/2026-07-17-ky-snap-manual` already holds Volume II
(SNAP) and Volume IIA (SNAP work requirements) in full (400 page provisions); #680's 2 "captured" is
a document count. What is blocked is the index re-check for newer OMTL editions or further volumes.

**us-ny** — https://otda.ny.gov/programs/snap/: the plain Axiom request is reset (curl 56,
connection reset by peer, 30 s timeout); curl-cffi chrome120 impersonation gets HTTP 200 carrying a
5,609-byte F5/TSPD JavaScript bot-challenge page instead of the program page, so no index inventory
is possible. The released scopes hold the 576-page SNAP Source Book, the 16-part Employment Policy
Manual (340 provisions) and 18 NYCRR Parts 385 and 387 (1,678 provisions); #680's 18 "captured" is a
document count. OTDA policy directives (ADM/INF/GIS) remain a separate family to inventory when the
host answers.

## Artifacts (unsigned, uncommitted; `data/` is gitignored in the main checkout)

- `data/corpus/sources/us-xx/manual/2026-09-10-snap-state-manual-completion/official-documents/*.html`
- `data/corpus/inventory/us-xx/manual/2026-09-10-snap-state-manual-completion.json`
- `data/corpus/provisions/us-xx/manual/2026-09-10-snap-state-manual-completion.jsonl`
- `data/corpus/coverage/us-xx/manual/2026-09-10-snap-state-manual-completion.json`

for xx in tx, nh, under `/Users/pavelmakarchuk/axiom-corpus/data/corpus`.

Rebuild:

```bash
uv run python scripts/build_snap_state_manual_completion_manifests.py \
  --corpus-base /Users/pavelmakarchuk/axiom-corpus/data/corpus
for j in tx nh; do
  uv run axiom-corpus-ingest extract-official-documents \
    --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
    --version 2026-09-10-snap-state-manual-completion \
    --manifest manifests/us-$j-snap-manual-completion.yaml
done
```

`source_as_of` and `expression_date` are carried per document in the manifests (2026-09-10).

Ruff: `uv run ruff check scripts/build_snap_state_manual_completion_manifests.py` -> all checks passed.

Tests: `uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or snap"`
-> 274 passed, 63 failed, 3 skipped (4,202 deselected). All 63 failures are pre-existing data-dependent tests
that open `data/corpus/...` artifacts this sparse worktree does not check out: 59 `FileNotFoundError` and 2
`pymupdf.FileNotFoundError` on `data/corpus` paths, plus 2 existence assertions on the same paths
(`test_rulespec_be_source_snapshots_and_signed_manifests_are_complete`, and
`test_state_snap_queue_statuses_match_retained_sources` failing at `us-al:target` because
`data/corpus/sources/us-al/...` is absent, not because a queue status changed). The ten failures known from the
`manifest or official_documents or discovery` selection (BE rulespec promotion, NY TANF compatibility x2, BE source
promotion, AK/CT/MI/MT/ND/NY SNAP manual tests) are among them; the other 53 are the per-state SNAP scope tests
(`tests/test_us_*_snap_*.py`, `test_corpus_massachusetts.py`, `test_state_snap_manual_queue.py`,
`test_uk_rulespec_release.py`, `test_us_rulespec_2026_08_08_obbb_alien_snap.py`) that the added `snap` keyword
selects and that need the same artifacts. No test reads the new manifests, the completion queue or the generator.

## Reviewer judgments (all of them)

1. Batch selection rule: the four ingestion-gap states, then TX, CA, NY by population and NH, KY,
   ME as the thinnest three.
2. FL, AL, MD, MA: the #680 gap is ingested-but-unqueued (registered regulation sections from
   Cornell LII republications with no encoding-queue item or artifact), not lost documents; no
   completion scope opened. The Cornell LII regulation manifests (`us-fl-snap-primary-policy.yaml`,
   `us-al-snap-primary-policy.yaml`, `us-ma-snap-primary-policy.yaml`, `primary_source: false`)
   are non-primary republications under this queue's forbidden-sources policy; replacing them with
   the official state register text (flrules.org FAC 65A-1, Ala. Admin. Code 660-4, 106 CMR from
   mass.gov) is a separate work order.
3. MA: `us-ma/regulation/106-cmr/364/360` (the one registered path absent from the consolidated
   scope) is treated as a Cornell LII artefact, not a missing official document; the DTA Online
   Guide is a separate family deferred to a discovery batch.
4. AL: the publisher index could not be re-checked today (connect timeout); the 2026-05-27 inventory
   of 17 chapters stands.
5. TX: Parts A, B, C and the glossary are the SNAP-governing family; Parts D-X (medical-only) are
   inventoried, not taken. Part R (refugee medical assistance) is listed as a part but the builder
   found 0 chapter pages under it, as today's Medicaid run also found; confirm on the live index.
6. TX content overlap with today's Medicaid run: `us-tx/manual/2026-09-10-medicaid-state-eligibility-manual`
   took the whole of TWH Part A under `us-tx/manual/hhsc/medicaid/twh-*` (156 pages: the 147 Part A
   pages taken here plus 9 already in the released SNAP scope). All 147 Part A source URLs in this
   scope are therefore also in the Medicaid scope under a different citation convention. There is
   no citation-path collision (0 shared paths), so a release accepts both; the same text appears
   twice in the corpus under two conventions, which the controller should either accept (each
   program's queue cites its own path) or resolve by dropping Part A from one of the two unreleased
   scopes before the selector is cut. Parts B and C and the glossary appear only here.
7. TX: the 12 sections already in released TX scopes keep their old citation paths and are not
   re-taken (11 counted under the taken parts; D-1820 lies in Part D).
8. TX: `expression_date` = fetch date (2026-09-10) for every section rather than the "Revision
   NN-N; Effective ..." line printed at the top of each section (the released TX scope and today's
   Medicaid TX scope do the same).
9. NH: `document_class: manual` and `us-nh/manual/dhhs/fsm/<topic>` follow the NH manual convention
   (today's TANF scope `us-nh/manual/dhhs/fam/<topic>`) rather than the released NH SNAP scope's
   `regulation` class, because the Food Stamp Manual is a policy manual, not He-W 700.
10. NH: topics are de-duplicated by topic file across the WebHelp books (861 TOC links -> 502
    topics); the 109 Service Release documents cited by the topics are a separate family, not
    taken; `expression_date` = fetch date rather than the per-topic "SR yy-nn Dated mm/yy" line.
11. NH: browser impersonation is used only as the existing manifest option (`request:
    browser_impersonation: true`), the same as the NH Family Assistance Manual scope; the host
    answers 403 to the plain user agent.
12. CA and ME: nothing to take; #680's counts for CA, ME, KY and NY are document counts, not
    section counts. ME: the index now links Ch. 609 as `144c609-2026-191-AMD.docx`, an amended
    edition newer than the released `144c609_0.docx`; its citation path
    `us-me/regulation/dhhs/ofi/chapter-609` already exists, so a completion scope cannot carry it
    and a superseding ME rules scope is needed instead.
13. KY and NY recorded as blocked from this network after one plain request and one
    browser-impersonation attempt each; no proxies, mirrors or archived copies.
14. Extraction seconds for TX and NH are derived from artifact timestamps, not from a timer, because
    the first session's log was lost.

## Remaining from #680

Discovery-gap states not yet attempted (in #680's order): NE, WY, AZ, AR, IA, HI, NM, VT, NV, ND,
ID, NC, OH, MT, OK, GA, TN, MI (18; TN and MI borderline, re-check against the publisher rather than
the threshold). KY and NY need a retry from another network or an official export. Follow-on
families: MA DTA Online Guide; NH Service Releases; TX TWH Parts D-X are medical-only and belong to
the Medicaid/CHIP queues; OTDA ADM/INF/GIS directives; FL quarterly Summary of Changes; ME Ch. 609
amended edition (superseding scope). Controller steps after review: `sign-ingest-manifest` per
scope, an immutable release selector, `publish_corpus.py --dry-run`, then publication and
activation; only then do the new TX and NH sections reach the encoding dashboard.
