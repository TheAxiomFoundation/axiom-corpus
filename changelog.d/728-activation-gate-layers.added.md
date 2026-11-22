The activation gate (`scripts/check_release_gate.py`) now reads scope layers.
`cut_plan_provenance` compares each scope's layer in the cut plan with its
layer in the signed object. The active-state preview uses a stored release
object only when it is the signed object of the row it was looked up under
(release name, recomputed content digest, and a schema and signature that
verify under the current release key, or, for a release the activation
displaces, under a retired key listed in
`AXIOM_CORPUS_RELEASE_LEGACY_PUBLIC_KEYS`), and it records each displaced
release's base version for the pair as `current_base_version`. An unverified
stored object can therefore no longer supply `scope_monotonicity`'s active
versions either. Three new activation checks refuse what the earlier checks
miss. `base_carry_forward` fails an activation that stops serving an active
base. It passes only when the incoming release selects that base unchanged, or
when a `base_replacements` entry for the incoming release, pinned at its
signed selector digest, records the replacement and the incoming release no
longer selects the replaced version. `base_only_pair` fails a pair that the
incoming release selects only as a base while the displaced release serves
primary scopes there. `primary_frontier` fails an activation that moves a
layered pair's newest primary scope back, which a base dated after the primary
scopes could hide from `scope_monotonicity`. `--allow-regression` softens
`primary_frontier` as it softens `scope_monotonicity`, and softens neither of
the other two. The gate refuses a preview row whose `current_release_name` is
null but which carries active-release evidence. The lineage baseline loader
now refuses a mapping that repeats a key. The gate runs its activation checks
only in the activation workflow, which does not yet pass the retired keys, and
judges serving as its preview read it; see "Activation gate" under "Successor
cuts" in `docs/named-release-publication.md` for its known limits.
