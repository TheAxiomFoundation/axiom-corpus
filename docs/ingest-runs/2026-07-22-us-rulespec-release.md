# 2026-07-22 US RuleSpec release selector

`us-rulespec-2026-07-22-current` advances the complete current US RuleSpec
selector from the reviewed 200-scope
`us-rulespec-2026-07-21-az-140es-current` boundary. It replaces two partial
federal Title 7 carriers with one consolidated scope:

- removed `us/statute/2026-05-10-snap-sections`
- removed `us/statute/2026-07-17-hr6644-dependency-closure-title-7-title-7`
- added `us/statute/2026-07-22-rulespec-title-7-consolidated`

The consolidation was generated with `scripts/consolidate_release_scopes.py`
from the complete 827-provision Chapter 51 scope and the 36-provision Title 7
dependency scope. It prefers the Chapter 51 carrier for their shared title
container, yielding 862 unique provisions: all of Chapter 51 plus sections 1928
and 1929 and their descendants. The four-section legacy SNAP scope is fully
subsumed by Chapter 51.

The resulting selector contains 199 unique, sorted
`jurisdiction x document_class x version` scopes. Publication must run from a
clean checkout of the merged selector commit and must pass the standard deep
validation, R2 readback, staged projection, signature, and activation-preview
gates before any production pointer changes.
