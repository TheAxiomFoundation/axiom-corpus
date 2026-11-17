Add `axiom_corpus.corpus.successors`: `compose_successor` builds a new cut from
its predecessor's selector and carries every base scope unchanged, and
`render_selector` writes the selector text a new cut commits. The selector
lineage check now reports a cut that does not carry its predecessor's base
scope unchanged (dropped base) and a primary scope moved into the base layer
(layer changed), and its baseline accepts reviewed `base_replacements`. The
release dedup never opens or cuts a base scope. Scope consolidation,
composition and repair refuse a scope a tracked selector marks as a base, and
`scripts/sign_release_scopes.sh` stops before it stages anything when a draft
adds a base scope, moves a scope between layers or misspells a layer. See
"Successor cuts" in `docs/named-release-publication.md`.
