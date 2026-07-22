# 2026-07-22 US RuleSpec release selector

`us-rulespec-2026-07-22-current` advances the complete current US RuleSpec
selector from the reviewed 200-scope
`us-rulespec-2026-07-21-az-140es-current` boundary. It preserves those scopes
exactly and adds the complete federal SNAP statute scope:

- `us/statute/2026-07-21-snap-chapter-51-title-7-title-7`

The resulting selector contains 201 unique, sorted
`jurisdiction x document_class x version` scopes. Publication must run from a
clean checkout of the merged selector commit and must pass the standard deep
validation, R2 readback, staged projection, signature, and activation-preview
gates before any production pointer changes.
