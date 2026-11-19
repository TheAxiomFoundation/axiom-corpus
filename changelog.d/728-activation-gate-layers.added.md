The activation gate (`scripts/check_release_gate.py`) now reads scope layers.
`cut_plan_provenance` compares each scope's layer in the tracked selector with
its layer in the signed object, and the active-state preview records each
displaced release's base version for the pair as `current_base_version`. Two
new activation checks fail closed. `base_carry_forward` fails an activation
that stops serving an active base, unless the incoming release selects that
base unchanged or a `base_replacements` entry for the incoming release, pinned
at its signed selector digest, records the replacement. `base_only_pair` fails
a pair that the incoming release selects only as a base while the displaced
release serves primary scopes there. `--allow-regression` softens neither
check. See "Activation gate" under "Successor cuts" in
`docs/named-release-publication.md`.
