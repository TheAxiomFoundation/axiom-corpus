# Program-bundle gaps, 2026-10-06

Every document the program bundles name that the served corpus does not hold, and the wave-6 work orders that close
them.

## How the list was made

- Bundles: `manifests/program-bundles/<program>.yaml` of axiom-corpus#780 at 8c14dbd3d (13 programs; a federal layer and
  51 state layers; Tier 1 = the PolicyEngine-US 2.29.11 references and the plan's documents, Tier 2 = all relevant
  documents).
- Measure: the axiom.org bundle collector (`scripts/collect-program-bundles.mjs`, axiom.org#311 at 731df72), dry run on
  2026-10-06 against the served corpus. A document is in the corpus when its root path is a served navigation node;
  state-law web pages are matched to a served section by their section number. 3,082 in-scope documents are not.
- `missing.json`: those 3,082 documents (identity = corpus path, or web address), with programs, tiers, layer and the
  number of provisions PolicyEngine cites in each.
- `buckets.json`: 67 are on open PRs (`pr`), 302 are named by a manifest on main that no served scope holds (`main`), the
  rest are nowhere yet (`rest`).
- `triage.json`: one plain GET per address with the corpus user agent (no retries), the publisher kind (official,
  mirror, vendor, other) and the status.

## On open PRs (no wave-6 action)

#716 (wave 5 tax) 21, #717 (wave 5 TANF/CCDF) 14, #778 (Kansas LIEAP) 14, #763 (SNAP child support sources) 11,
#753 (D.C. title 47) 4, #754 (Maine) 2, #714 (wave 5 Medicaid/CHIP) 1.

## Wave 6

`wave6/00-common-preamble.md` (rules for every agent), one brief and one CSV per group. 3,015 documents, 2,694 in
Tier 1:

| group | documents |
|---|---:|
| federal | 333 |
| tax-al-hi | 399 |
| tax-ia-mi | 404 |
| tax-mn-oh | 379 |
| tax-ok-wv | 394 |
| tanf-ccdf-ak-ne | 372 |
| tanf-ccdf-nh-wy | 341 |
| health | 128 |
| benefits | 265 |

Each agent writes `docs/ingest-runs/2026-10-06-w6-<group>-decisions.csv`, one row per CSV row, with the new status and
the scope and path that hold the document. Those rows join the bundles to the new documents when an official address
differs from the bundle's.
