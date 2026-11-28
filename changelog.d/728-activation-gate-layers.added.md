The activation gate (`scripts/check_release_gate.py`) now reads scope layers.
`cut_plan_provenance` compares each scope's layer in the cut plan with its
layer in the signed object. The live active-state preview takes each pair's
active versions, base and publication time only from a stored release object
it has verified as the signed object of the row it was looked up under
(release name, recomputed content digest, and a schema and signature that
verify under the current release key, or, for a release the activation
displaces, under a retired key listed in
`AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS`), and it records each displaced
release's base version for the pair as `current_base_version`. It refuses a
preview row that does not have exactly the preview function's five columns, a
stored-object response that is not a list of rows with the query's four
columns, each naming a release the query asked for, and none twice, and a
response that lacks the stored object of a release the activation displaces;
each refusal fails every active-state check. In the live preview, neither an
unverified stored object nor a field of the database response can therefore
supply `scope_monotonicity`'s active versions. Like the publisher, the gate
refuses a retired-key list that includes the current key or names one key
twice in different spellings. Three new activation checks refuse what the
earlier checks miss. Each compares the incoming release, pair by pair, with
the release that serves the pair now, wherever the pair's preview row has
`changes` true. `base_carry_forward` fails an activation that stops serving
that release's base. It passes only when the incoming release selects that
base unchanged, or when a `base_replacements` entry for the incoming release,
pinned at its signed selector digest, records the replacement and the incoming
release no longer selects the replaced version. `base_only_pair` fails a pair
that the incoming release selects only as a base while the displaced release
serves primary scopes there. `primary_frontier` fails an activation that moves
a layered pair's newest primary scope back, which a base dated after the
primary scopes could hide from `scope_monotonicity`. `--allow-regression`
softens `primary_frontier` as it softens `scope_monotonicity`, and softens
neither of the other two. The gate refuses a preview row whose
`current_release_name` is null but which carries active-release evidence. The
lineage baseline loader now refuses a mapping that repeats a key or gives the
merge key (`<<`) twice. Of the workflows, only the activation workflow runs
the gate's activation checks, and it passes the retired keys to both of its
gate steps. The gate judges serving as its preview read it; see "Activation
gate" under "Successor cuts" in `docs/named-release-publication.md` for its
known limits.
