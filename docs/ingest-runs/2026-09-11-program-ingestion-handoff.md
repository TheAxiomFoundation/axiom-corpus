# Program ingestion hand-off (2026-09-10 to 2026-09-11)

Controller hand-off for the board Year 1 program ingestion. Everything below is committed and
pushed to TheAxiomFoundation/axiom-corpus; nothing is signed or published. Corpus artifacts
(`data/corpus/{sources,inventory,provisions,coverage}`) exist only on the controller's machine
(`data/` is gitignored) and are unsigned.

## Branches and pull requests

| Program | Branch | Draft PR | Run notes (`docs/ingest-runs/`) |
| --- | --- | --- | --- |
| base: work orders + LIHEAP | `discovery/committed-program-work-orders` | #670 (to main) | `2026-09-10-liheap-state-plans-fy2026.md` |
| SSI | `discovery/ingest-ssi` | #671 | `2026-09-10-ssi-poms-si.md`, `2026-09-10-ssi-state-supplements-batch-{1,2,3}.md` |
| Medicare | `discovery/ingest-medicare` | #672 | `2026-09-10-medicare-cms-iom-100-01.md`, `-100-24.md` |
| Tax | `discovery/ingest-tax` | #673 | `2026-09-10-tax-forms-instructions-guidance-batch-{1,2,3-retry}.md` |
| CHIP | `discovery/ingest-chip` | #674 | `2026-09-10-chip-state-eligibility-manuals{,-batch-2,-batch-3,-batch-4-retry}.md` |
| TANF | `discovery/ingest-tanf` | #675 | `2026-09-10-tanf-state-policy-manuals-batch-{1,2,3,4-retry}.md` |
| WIC | `discovery/ingest-wic` | #676 | `2026-09-10-wic-fns-guidance-and-state-manuals.md`, `2026-09-10-wic-state-manuals-batch-{2,3,4-retry,5}.md` |
| CCDF | `discovery/ingest-ccdf` | #677 | `2026-09-10-ccdf-state-plans-fy2025-2027{,-retry,-retry-2}.md` |
| Medicaid | `discovery/ingest-medicaid` | #678 | `2026-09-10-medicaid-state-eligibility-manuals-batch-{1,2,3,4-retry,5}.md` |
| SNAP completion (#680) | `discovery/ingest-snap` | #681 | `2026-09-10-snap-state-manual-completion-batch-{1,2,3}.md` |

The program PRs are stacked on the base branch. CI only runs for PRs against `main`, so either
merge #670 first or retarget the program PRs to `main`. All generator scripts pass `ruff`.
Cross-branch pointers: CHIP rows for LA, OH, SC, KS, AZ, NC, NJ, VA, AR and SSI rows for TX, ID
point at Medicaid- or CHIP-branch scopes, so those branches must merge together.

## Per-jurisdiction state

Each program queue (`manifests/<program>-agent-queue.yaml`, `manifests/snap-completion-agent-queue.yaml`)
carries one row per jurisdiction with `queue_status` (`agent_ready` = extracted, `done` = already in
the corpus by pointer, `blocked_primary_source` = exact failure recorded, `needs_review`),
`index_url`, `index_document_count`, `taken_count`, and index families. Every run note lists every
reviewer judgment. Blocks that survive a US-exit network are publisher bot walls (NY OTDA/OCFS,
CA DHCS, AZ DES, MO, MD, GA, TX AWS WAF) or agencies that post no manual; they are not
worked around. Issue #680's "ingestion gap" for FL, AL, MD, MA is a counting artifact (ingested
regulation sections never queued for encoding), not lost documents; its thin states are now either
completed (TX, NH, KY, WY, ND) or confirmed complete against their publishers.

## Controller steps

Update 2026-09-11 (second pass): the selector collisions are resolved and the branches are
verified to merge; see `2026-09-11-release-consolidation.md`. The draft successor selector
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`
(`us-rulespec-2026-09-11-program-ingestion-union`, 536 scopes, 263 unreleased) deep-validates
with zero errors. The Colorado, Ohio and Maryland collisions became three consolidated successor
scopes built with `scripts/consolidate_release_scopes.py`; the Medicaid branch's CRLF copy of the
DigiCert G2 intermediate was normalized so all ten branches merge onto `main` without conflict.

1. Review and merge the PRs (#670 first; all CI jobs on it are green).
2. On a clean branch cut from `main` after the merges, with `AXIOM_CORPUS_INGEST_PRIVATE_KEY`
   exported in the shell (never in a file), run
   `scripts/sign_release_scopes.sh docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json manifests/releases/us-rulespec-2026-08-23-canada-338-suspension-union.json`.
   It force-adds the 263 unreleased scopes' artifacts (about 2.2 GB) and commits them, signs each
   scope against that commit, commits the signed manifests under `.axiom/ingest-manifests/`,
   self-verifies with `guard-ingested` when `AXIOM_CORPUS_INGEST_PUBLIC_KEY` is exported, then
   copies the draft to `manifests/releases/<name>.json`, deep-validates it and commits it.
   Open a PR; CI runs `guard-ingested` and validates the selector.
3. `uv run --extra dev python scripts/publish_corpus.py --release manifests/releases/us-rulespec-2026-09-11-program-ingestion-union.json --dry-run`,
   then dispatch `activate-release.yml` and approve the `release-preview` and `release-activation`
   environments.
4. Advisory `unsectioned_document_body` warnings (GA, IA, KY, MD, OR single-body documents) can
   be split later with `section-provisions`; they do not block.

## Final per-jurisdiction tally

Extracted / done by pointer / blocked, over the 50 states plus DC: LIHEAP 51/0/0 · Medicaid 41/6/3
(AL, CA, NE; WY needs_review) · CCDF 43/0/6 (AZ, GA, MD, MO, NY, TX; AK and IN post no conforming plan)
· CHIP 33/13/5 (CA, DC, FL, MT, WY) · SSI 27/22/2 (NY, WY) · TANF 24/26/1 (NY) · WIC 21/0/30 (7 access
blocks, 3 behind login, 20 publish no manual) · tax 17/34/0 · SNAP completion 5/20/3 (AZ, NY,
OH eManuals) · Medicare federal only (IOM Pub 100-01 and Pub 100-24). Every jurisdiction has a resolved
row in every program queue.

## Open reviewer decisions

- The consolidation choices above are reversible until signing: the released Colorado recovery
  and Ohio OAC 5101:4 scopes are replaced in the selector by successors that fold in the new
  scopes (Colorado keeps the section-level TANF text for 3.606.1, 3.606.2 and 3.606.6 over the
  recovery scope's page fragments). To reject, delete the three consolidated versions from
  `data/corpus` and restore the originals in the draft selector.
- `manual` vs `regulation` for codified rules ingested as `manual` under the work order (NJ, MA, CO,
  OK, OH, NM Medicaid); precedents used `regulation`.
- Texas Works Handbook Part A text sits in both the Medicaid scope and the SNAP completion scope
  under different path conventions.
- Revised editions found during the SNAP completion pass (NC, GA, TN, OK, MI, KY, NE, AR, NV, WY,
  ND, ME) need superseding scopes; released scopes are immutable.
- WIC DC `source_as_of` is 2026-09-11 while the other WIC scopes carry 2026-09-10.
