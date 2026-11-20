Add `axiom_corpus.corpus.successors`: `compose_successor` builds a new cut from
its predecessor's selector and carries every base scope unchanged, and
`render_selector` writes the selector text a new cut commits. The composer
reads the tracked selectors of the checkout the cut is committed to
(`releases_dir`), refuses a directory that does not hold the predecessor as
given, and refuses a new primary scope that a tracked selector marks as a base.
The selector lineage check now reports a cut that does not carry its
predecessor's base scope unchanged (dropped base), a primary scope moved into
the base layer (layer changed), and a scope one tracked selector selects as a
base and another as a primary scope (layer conflict). Its baseline accepts
reviewed `base_replacements` for a base the cut no longer selects, and the
check holds entries built in code to the file's rules. The release dedup never
opens or cuts a base scope the target declares, and refuses a target that
selects a tracked base as a primary scope. Scope consolidation, composition and
repair refuse a scope a tracked selector marks as a base and a scope name a
selector could not spell, and repair also refuses a new scope its own release
selector marks as a base. On the command line, consolidation, composition and
dedup read the tracked selectors of the checkout holding `--base` or
`--corpus`. `scripts/sign_release_scopes.sh` stops before it stages anything
when either selector misspells a scope or lists one twice, or when a draft adds
a base scope, moves a scope between layers, misspells a layer or selects a
tracked base as a primary scope. See "Successor cuts" in
`docs/named-release-publication.md`.
