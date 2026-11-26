Add `axiom_corpus.corpus.successors`: `compose_successor` builds a new cut from
its predecessor's selector and carries every base scope unchanged, and
`render_selector` writes the selector text a new cut commits. The composer reads
the tracked selectors of the checkout the cut is committed to (`releases_dir`),
refuses a directory that does not hold the predecessor as given, and refuses a
new primary scope that a tracked selector of that checkout marks as a base. The
selector lineage check now reports a cut that does not carry its predecessor's
base scope unchanged (dropped base), a primary scope moved into the base layer
(layer changed), and a scope one tracked selector selects as a base and another
as a primary scope (layer conflict). Its baseline accepts reviewed
`base_replacements` for a base the cut no longer selects, and the check holds
entries built in code to the loader's shape rules. The release dedup never opens
or cuts a base scope the target declares, and refuses a target that selects a
tracked base as a primary scope. Scope consolidation, composition and repair
refuse a scope a tracked selector they read marks as a base and a scope name a
selector could not spell, and repair also refuses a new scope its own release
selector marks as a base. On the command line, consolidation, composition, the
CA builder and dedup read the tracked selectors of the checkout
`resolver.cli_repo` finds from `--base` or `--corpus`.
`scripts/sign_release_scopes.sh` stops before it stages anything when either
selector misspells a scope or lists one twice, or when a draft adds a base
scope, moves a scope between layers, misspells a layer or selects a tracked base
as a primary scope. Tracked selectors are read as committed at HEAD; a selectors
directory reached through a link, such as a `manifests` linked to another
checkout's, or one at which git would read another repository (a nested
repository or a gitfile, or a `core.worktree` setting where the tool is given
that checkout's own selectors directory; the threat model's limit 11), is
refused. Dedup, consolidation, composition, repair and the CA builder also read
the selectors of the working directory's checkout, of the checkouts that
physically hold their artifacts, and of each checkout the resolver recognises
that holds a directory link on the paths they use, as they spell them. They
refuse an artifact path that does not resolve to a path ending in its own
artifact kind, jurisdiction, document class and version, a rewritten file with
another hard link, a corpus link into no checkout, and a path through a
symlinked file at or below a guarded place of a checkout the resolver
recognises; dedup, repair and CA promotion also refuse to rewrite, move or
unlink a file that a base they know reaches through a link. Repair refuses a
report path that lies at or below a corpus, lock or selector place of `--repo`,
of the checkout that physically holds it, or of a checkout that holds a link at
one of its guarded places on the path as spelled, wherever that place leads, and
one below an entry that is not a directory; one that is not a regular file
(`/dev/null` included), and one over a file it did not write, and never writes
the report through a link. The composer refuses to rewrite a tracked selector.
The CA builder refuses a base in its selector and in-place promotion of a base.
The signer checks that its predecessor is the committed selector the draft names
first and, when a merge base with main exists, that one of those merge bases has
it unchanged; it loads both selectors with the selector parser and reports a
selector it cannot read in one line. The threat model in
`docs/named-release-publication.md` defines what these checks read and lists
what they do not check. See "Successor cuts" in
`docs/named-release-publication.md`.
