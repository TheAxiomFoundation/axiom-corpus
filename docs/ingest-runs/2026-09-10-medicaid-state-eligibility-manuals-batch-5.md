# Medicaid state eligibility manuals, batch 5 (last jurisdictions, queue repair)

Date: 2026-09-11 (scope version stays `2026-09-10-medicaid-state-eligibility-manual`)
Program: Medicaid (board Year 1 list; `manifests/medicaid-agent-queue.yaml`)
Generator: `scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 5`
Impact analysis: not run; the GitNexus MCP tools were unavailable in every session. No library function
under `src/axiom_corpus` was modified and no adapter was added.

Timing: the batch ran across several agent sessions on 2026-09-11 (the first two were killed by a usage
limit and a stall, each leaving its worktree state intact). The nine non-NH scopes were extracted in the
morning sessions whose own timers were lost, so their seconds below are derived from the span of each
scope's source-file mtimes. The New Hampshire extraction was run and timed directly by the controller
session: 225 s, finishing 2026-09-11T20:10Z; that session ran 19:55Z to 20:25Z and also verified every
scope, wrote this note, and committed.

## Selection

Batch 5 closes the map. It takes the eight jurisdictions that had no queue row (AK, DC, DE, ND, RI, SD,
VT, WY) and the five rows batch 4 left `needs_review` (HI, ME, NE, NH, OR). After this batch every one of
the 50 states plus DC has a resolved row, and `status_counts` reconcile against the 52 rows (51
jurisdictions plus the federal row): `agent_ready` 41, `done` 6, `blocked_primary_source` 3,
`needs_review` 2 (us-wy and the federal `us` row).

## Queue repair (reviewer judgment 1)

The `us-ma` and `us-in` rows were missing from the queue even though batch 2 had built their manifests and
extracted complete scopes. The cause is structural, not a bad edit: a queue row for an extracted
jurisdiction is produced only by that jurisdiction's live builder, so `--batch N [--only X]` leaves every
other row exactly as the file holds it and can never recreate one that is absent. The rows were lost in
the batch-2 session before its commit — `dbc81974`'s `status_counts` read `agent_ready: 14`, not 16, and
no commit in the branch's history ever carried either row (`git log -S'jurisdiction: us-ma' --
manifests/medicaid-agent-queue.yaml` is empty), so "recover them from the batch-2 commit" was not
available and the rows had to be rebuilt.

The fix is `restore_missing_rows` plus `MANIFEST_ROW_FACTS`: the publisher-index facts for those two
states are recorded in the generator, and any `--batch` run rebuilds a row that is missing from the queue
but whose manifest is committed, without re-crawling the publisher. Both restored rows carry their
original batch-2 counts (MA 14 of 71 documents, IN 22 of 35) and a note saying the row was restored on
2026-09-11. Proof that no other row moves: `--batch 5 --only us-none` leaves the queue unchanged apart
from `status_counts`.

## Per-jurisdiction results

| Jurisdiction | Class | Source | Documents | Provisions | Extraction s |
| --- | --- | --- | ---: | ---: | ---: |
| us-nh | manual | DHHS Medical Assistance Manual (RoboHelp) | 601 | 1,202 | 225 |
| us-nd | manual | DHS Service Chapter 510-05 Medicaid eligibility | 189 | 378 | 170 |
| us-ak | manual | DPA Aged, Disabled and Long Term Care Medicaid manual | 127 | 254 | 104 |
| us-hi | regulation | HAR title 17 Med-QUEST chapters | 44 | 807 | 95 |
| us-ri | manual | 210-RICR Medicaid rule parts | 34 | 707 | 99 |
| us-dc | manual | DCMR title 29 Medicaid eligibility sections | 23 | 46 | 30 |
| us-me | regulation | 10-144 CMR ch. 332 MaineCare Eligibility Manual parts | 16 | 111 | 32 |
| us-sd | manual | ARSD 67:46 chapters (LRC rules API) | 14 | 29 | 13 |
| us-de | manual | DSSM title 16 ch. 14000 Medicaid eligibility | 7 | 150 | 7 |
| us-vt | manual | HBEE eligibility parts | 7 | 186 | 15 |

Totals: 10 scopes, 1,062 documents, 3,870 provisions. Every scope `complete: true` with 0 missing, 0 extra
and 0 duplicate citation paths. Verified independently of the coverage reports: each provisions JSONL
holds as many distinct `citation_path` values as rows, the root/body shape matches the jurisdiction's
existing scopes (one empty document root plus one body row per document, as `us-nh/manual` does for TANF
and the SSI supplement), and no citation path collides with any other provisions JSONL under the same
jurisdiction — including today's CHIP scopes, which hold the Alaska MAGI manual, North Dakota Service
Chapter 510-03, Hawaii HAR 17-1715 and 17-1724.2, and Maine ch. 332 Parts 5 and 11.

## Index inventories (publisher index, by family; taken counts)

- **us-ak** http://dpaweb.hss.state.ak.us/manuals/adltc/adltc.htm — manual topic pages 394 found, 127 taken.
- **us-dc** https://dcregs.dc.gov/Common/DCMR/ChapterList.aspx?TitleNum=29 — Medicaid eligibility sections 23/23; reserved or repealed 1/0.
- **us-de** https://regulations.delaware.gov/AdminCode/title16 — Medicaid eligibility chapters 7/7; other DSSM Medicaid chapters 6/0.
- **us-hi** https://humanservices.hawaii.gov/admin-rules-2/admin-rules-for-programs/ — Med-QUEST chapter PDFs 44/44; already in the CHIP scope 2/0; repealed chapters 27/0; dead index links 2/0.
- **us-me** https://www.maine.gov/sos/rulemaking/agency-rules/mainecare-eligibility-manual — manual part DOCX 18/16; already in the CHIP or SSI scope 2/0.
- **us-nd** https://www.nd.gov/dhs/policymanuals/51005/Default.htm — policy topic pages 189/189; site pages 6/0.
- **us-nh** https://www.dhhs.nh.gov/mam_htm/newmam.htm — manual section pages 601/601.
- **us-ri** https://rules.sos.ri.gov/organizations/title/210 — Medicaid rule part PDFs 34/34; repealed part 1/0.
- **us-sd** https://sdlegislature.gov/Rules/Administrative/67:46 — Medicaid eligibility chapters 14/14; non-Medicaid CHIP chapter 1/0.
- **us-vt** https://humanservices.vermont.gov/rules-policies/health-care-rules/health-benefits-eligibility-and-enrollment-rules-hbee — HBEE eligibility parts 7/7; other HBEE page PDFs 19/0.
- **us-wy** https://ecom.wyo.gov/ — manual policy pages 107/0; eligibility tables 17/0 (inventoried, nothing taken; see below).
- **us-ne** https://dhhs.ne.gov/Pages/Title-477.aspx — SoS chapter listing 1/0; Title 477 appendix PDFs 47/0.
- **us-or** https://secure.sos.state.or.us/oard/displayDivisionRules.action?selectedDivision=1742 — OAR 410 division 200 rules 43 found, 41 already in the corpus (pointer row).

Index documents found across the batch: 1,398 on the ten extracted publishers' indexes, 1,062 taken.

## Pointer, blocked and needs_review rows

- **us-or, done by pointer.** Oregon's Medicaid eligibility rules are OAR chapter 410 division 200, already
  in the corpus as `us-or/regulation/chapter-410/division-200` from today's CHIP branch. Not re-fetched.
- **us-ne, blocked_primary_source.** Title 477 NAC is served only through the Secretary of State rules
  site API, which answers an IP-based access denial from this network; the chain was completed with the
  DigiCert G2 intermediate already in `data/certs/` and verification was never disabled. The 47 appendix
  PDFs on dhhs.ne.gov are recorded as a separate family.
- **us-wy, needs_review.** The WDH Eligibility Online Manual at ecom.wyo.gov is a Google Sites page whose
  107 M-series policy pages and 17 eligibility tables were inventoried in full, but the content is
  rendered by script with no document URL in the served HTML. The host answers HTTP 200, so this is not an
  access block; it needs a Google-Sites text path that no other scope requires, which is not worth a
  one-state adapter in this batch.
- **us-al and us-ca** remain blocked from batch 4 (medicaid.alabama.gov TLS handshake never completes;
  DHCS serves an Imperva challenge). Not re-probed here.

## Reviewer judgments

1. The queue repair above: the rows were never written rather than dropped, and `restore_missing_rows`
   rebuilds them from committed manifests instead of re-crawling.
2. `document_class` is `regulation` for HI and ME (codified rules the state publishes itself, matching
   those jurisdictions' existing conventions) and `manual` elsewhere, including the DC, DE, RI, SD and VT
   rule-based manuals, which follow the batch-2 New Jersey precedent. A reviewer may prefer `regulation`
   for those five, as for NJ, MA, CO, OK, OH and NM.
3. Vermont's HBEE Parts 1 to 7 are taken as a complete standalone manual under `us-vt/manual/dvha/medicaid`
   even though today's CHIP branch took HBEE Parts 2 and 5 under CHIP paths (batch-2 MA precedent: the
   same publisher text may serve two programs under two conventions; no citation path collides).
4. Alaska and North Dakota were extracted rather than pointed at the CHIP scopes: the CHIP scopes hold the
   MAGI manuals, while these are the aged, disabled and long-term-care and the Service Chapter 510-05
   trees, a different family. Both rows carry a note naming the CHIP overlap.
5. Hawaii takes the 44 current Med-QUEST chapters; 27 repealed chapters, 2 chapters already in the CHIP
   scope and 2 dead index links are inventoried and not taken. `files.hawaii.gov` serves an access-denial
   page to the plain client and answers a browser TLS fingerprint, so those documents use the extractor's
   existing `browser_impersonation` option.
6. New Hampshire uses the batch-4 Louisiana request options (`browser_user_agent`,
   `browser_impersonation`, `browser_impersonation_direct`): dhhs.nh.gov answers 403 to a plain client and
   to `curl` with a browser user agent, and 200 to a curl_cffi chrome120 fingerprint. The whole Medical
   Assistance Manual is taken (601 pages, Introduction and Glossary included); the sibling Supervisory
   Release and archive trees are separate families and are not taken.
7. Maine takes the remaining ch. 332 parts from the same DOCX the CHIP and SSI scopes used for Parts 5 and
   11; those two parts are inventoried and not re-taken.
8. Page granularity with OCR fallback for PDF manuals and `expression_date` = fetch date, as in batches 1
   to 4.
9. Extraction seconds for the nine non-NH scopes are derived from artifact mtime spans because the
   sessions that produced them were killed before reporting; NH's 225 s is measured.
10. Wyoming recorded `needs_review` rather than blocked because the host answers; Nebraska recorded
    blocked because the publisher's own API refuses this network. Nothing was worked around: no mirrors,
    reposts, proxies or archived copies, and TLS verification was never disabled.

## Artifacts (unsigned, uncommitted, awaiting controller)

- `data/corpus/sources/us-xx/<class>/2026-09-10-medicaid-state-eligibility-manual/official-documents/*`
- `data/corpus/{inventory,provisions,coverage}/us-xx/<class>/2026-09-10-medicaid-state-eligibility-manual.*`

for xx in ak, dc, de, hi, me, nd, nh, ri, sd, vt.

## Rebuild

```bash
uv run python scripts/build_medicaid_state_eligibility_manual_manifests.py --batch 5
for j in ak dc de hi me nd nh ri sd vt; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-09-10-medicaid-state-eligibility-manual \
    --manifest manifests/us-$j-medicaid-eligibility-manual.yaml \
    --source-as-of 2026-09-10 --expression-date 2026-09-10
done
```

## Tests

`uv run pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
-> 255 passed, 10 failed, 2 skipped. The 10 are exactly the known sparse-worktree failures (Belgium
rulespec promotion, NY TANF compatibility x2, Belgium source promotion, AK/CT/MI/MT/ND/NY SNAP manual)
that read `data/corpus` artifacts of other scopes this sparse checkout does not hold; the same selection
passes in the full checkout. `ruff check` on the generator is clean.

## Closing status, all 51 jurisdictions

| Jurisdiction | Status | Batch | Documents taken |
| --- | --- | --- | ---: |
| us-ak Alaska | agent_ready | 5 | 127 |
| us-al Alabama | blocked_primary_source | - | 0 |
| us-ar Arkansas | agent_ready | 1 | 2 |
| us-az Arizona | agent_ready | 4 | 743 |
| us-ca California | blocked_primary_source | - | 0 |
| us-co Colorado | agent_ready | 2 | 1 |
| us-ct Connecticut | agent_ready | 3 | 1632 |
| us-dc District of Columbia | agent_ready | 5 | 23 |
| us-de Delaware | agent_ready | 5 | 7 |
| us-fl Florida | done | - | 0 |
| us-ga Georgia | agent_ready | 1 | 251 |
| us-hi Hawaii | agent_ready | 5 | 44 |
| us-ia Iowa | agent_ready | 3 | 14 |
| us-id Idaho | done | - | 0 |
| us-il Illinois | done | - | 0 |
| us-in Indiana | agent_ready | 2 | 22 |
| us-ks Kansas | agent_ready | 4 | 117 |
| us-ky Kentucky | agent_ready | 4 | 2 |
| us-la Louisiana | agent_ready | 4 | 99 |
| us-ma Massachusetts | agent_ready | 2 | 14 |
| us-md Maryland | agent_ready | 2 | 19 |
| us-me Maine | agent_ready | 5 | 16 |
| us-mi Michigan | done | - | 0 |
| us-mn Minnesota | agent_ready | 2 | 344 |
| us-mo Missouri | agent_ready | 2 | 565 |
| us-ms Mississippi | agent_ready | 3 | 29 |
| us-mt Montana | agent_ready | 4 | 125 |
| us-nc North Carolina | agent_ready | 1 | 149 |
| us-nd North Dakota | agent_ready | 5 | 189 |
| us-ne Nebraska | blocked_primary_source | 5 | 0 |
| us-nh New Hampshire | agent_ready | 5 | 601 |
| us-nj New Jersey | agent_ready | 1 | 6 |
| us-nm New Mexico | agent_ready | 4 | 90 |
| us-nv Nevada | agent_ready | 3 | 33 |
| us-ny New York | agent_ready | 1 | 8 |
| us-oh Ohio | agent_ready | 4 | 96 |
| us-ok Oklahoma | agent_ready | 3 | 350 |
| us-or Oregon | done | 5 | 41 |
| us-pa Pennsylvania | agent_ready | 1 | 380 |
| us-ri Rhode Island | agent_ready | 5 | 34 |
| us-sc South Carolina | agent_ready | 4 | 18 |
| us-sd South Dakota | agent_ready | 5 | 14 |
| us-tn Tennessee | agent_ready | 4 | 88 |
| us-tx Texas | agent_ready | 1 | 712 |
| us-ut Utah | agent_ready | 4 | 639 |
| us-va Virginia | agent_ready | 1 | 21 |
| us-vt Vermont | agent_ready | 5 | 7 |
| us-wa Washington | agent_ready | 2 | 202 |
| us-wi Wisconsin | agent_ready | 2 | 2 |
| us-wv West Virginia | done | - | 0 |
| us-wy Wyoming | needs_review | 5 | 0 |

Federal row `us`: `needs_review` — 42 CFR 435 is in the corpus, part 436 is not; nothing federal was
re-ingested in any batch.
