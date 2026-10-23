# Wave 8: the two live section 1115 demonstrations the wave-5 rule excluded

Date: 2026-10-20. Program: Medicaid. Branch `discovery/ingest-w8-medicaid-1115-bh`,
cut from `main` and rebased onto `discovery/ingest-w8-medicaid` so that branch's row
changes are preserved.

## Why these two

Earlier the same day, a re-probe of the six section 1115 queue rows (AK, ID, ND, NE,
NV, SC) found nothing current to take: every listing printed a status of pending,
expired, withdrawn or terminated. Two exceptions were deliberately left for this
assignment, because they are live but fall outside the `cms_1115_stc` family's
selection rule:

- Alaska Behavioral Health Reform, approval with technical correction of 2026-03-27.
- Idaho Behavioral Health Transformation, approval of 2024-03-29 with the amendment
  approval of 2025-05-15.

Both are service-authority demonstrations. The wave-5 rule for `cms_1115_stc`
excludes service authority, so taking them under that family would have broken the
rule, and leaving them would have lost live primary sources.

## Family boundary (reviewer judgment 1)

They are taken as a **sibling family**, not as an extension of `cms_1115_stc`. The
existing family keeps its rule intact and its released version untouched; the new
family is separable by a consumer at the citation root. Roots:

- existing: `us-xx/policy/cms/1115-stc/...`
- new: `us-xx/policy/cms/1115-service-authority/...`

Version `2026-10-20-w8-medicaid-1115-service-authority`, document_class `policy`,
publisher CMS. The existing family's `2026-09-15-medicaid-1115-stc` sits in two
signed releases and was not touched.

## Scopes

| jurisdiction | documents | provisions | extraction s |
| --- | ---: | ---: | ---: |
| us-ak | 1 | 209 | 51 |
| us-id | 3 | 138 | 74 |

Both scopes `complete: true`, 0 missing, 0 extra, 0 duplicate citation paths.
Verified independently of the coverage report: every row's citation path is distinct
(209 of 209 and 138 of 138), and no path collides with any other provisions JSONL
under the jurisdiction. The empty bodies are exactly the document roots, one per
document, which is the convention in every official-documents scope.

Index: the CMS demonstration and waiver list posts 66 documents for Alaska and the
Idaho page its own set; 1 and 3 taken respectively, being the approval documents the
publisher posts as current. A withdrawn or superseded approval was not taken.

## How this run was completed

The agent that built the manifests, the generator and the queue rows was stopped by a
usage limit immediately before extracting. The controller ran the two extractions,
verified both scopes, and wrote this note. Nothing in the manifests, the generator or
the queue rows was changed after the agent stopped, so the recorded index inventories
are that agent's work.

Reachability was judged from response bodies throughout, not status lines. Requests to
medicaid.gov were paced, because a burst draws a short access-denied body.

## Artifacts (unsigned, uncommitted)

`data/corpus/{sources,inventory,provisions,coverage}/us-{ak,id}/policy/2026-10-20-w8-medicaid-1115-service-authority.*`

## Rebuild

```bash
uv run python scripts/build_medicaid_1115_service_authority_manifests.py
for j in ak id; do
  uv run axiom-corpus-ingest extract-official-documents --base data/corpus \
    --version 2026-10-20-w8-medicaid-1115-service-authority \
    --manifest manifests/us-$j-medicaid-1115-service-authority.yaml \
    --source-as-of 2026-10-20
done
```

## Remaining

The other four section 1115 rows (ND, NE, NV, SC) stay under review with nothing
current to take. GitNexus MCP tools were unavailable, so no impact analysis ran, and
no function under `src/` changed.
