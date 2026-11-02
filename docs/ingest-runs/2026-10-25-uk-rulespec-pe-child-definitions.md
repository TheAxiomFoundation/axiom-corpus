# uk-rulespec-2026-10-25-pe-child-definitions: release selector

Date: 2026-10-25. Selector `manifests/releases/uk-rulespec-2026-10-25-pe-child-definitions.json`,
built by `scripts/repro/uk_rulespec_2026_10_25_pe_child_definitions.py` and checked by
`tests/test_uk_rulespec_2026_10_25_pe_child_definitions.py`.

## What it is

rulespec-uk's corpus pin, `uk-rulespec-2026-09-07` (191 scopes; rulespec-uk `.axiom/toolchain.toml`
on `main`), plus exactly two scopes. Both are signed and locked, and neither is withdrawn:

| Scope | Provisions | Ingested |
| --- | --- | --- |
| `uk/statute/2026-09-28-uk-pe-child-definitions` | 10 | `docs/ingest-runs/2026-09-28-uk-pe-child-definitions.md` |
| `uk/regulation/2026-09-28-uk-pe-child-definitions` | 27 | the same run note |

That makes 193 scopes, a strict superset of the pin. The scopes landed in axiom-corpus#765. They
carry each programme's legal definition of a child, qualifying or young person, couple, lone parent
and claimant, for the PolicyEngine parity work tracked by the rulespec-uk `pe-parity` issues. Their
provision files match the lock files on `main` (SHA256 `5a6df8e1…` statute, `7a7dac84…` regulation),
which include the 2026-10-23 regeneration recorded in that run note.

## Paths

A re-pin changes no existing resolution. The two scopes hold 37 citation paths, none repeated within
them, and none is carried by any of the pin's 191 scopes (checked against every pin scope's provision
file). The selector keeps the pin's quality profile, `complete-expression-dates-v1`. For that profile
`validate-release` requires every citation path to be unique across the release, and this selector is
not grandfathered from that check.

The pin selects no scope listed in `manifests/withdrawn-scopes.yaml`, and neither do the additions, so
this selector needs no withdrawn-scope exception.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin plus the two scopes, sorted. Each added scope is locked and not withdrawn.
- A Hypothesis property checks the build rule over arbitrary bases, including bases that already hold
  either addition.
- `axiom-corpus-ingest validate-release` with corpus data, on this selector and on the pin: both `ok`,
  0 errors and 0 warnings. Each reports the same one notice, the baselined `navigation_body` finding of
  `uk-broxtowe/manual/2026-09-05-broxtowe-council-tax-reduction-2026-2027`, which the pin already
  carries.
- CI's `Validate named release selectors` job repeats the deep validation.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`. **Publish only. Do not activate it.** It is a
   pin release for rulespec-uk; see `docs/named-release-publication.md`.
2. Re-pin rulespec-uk to this release. Four files name the corpus: `.axiom/toolchain.toml`
   (`axiom_corpus_release` and `axiom_corpus_release_content_sha256`),
   `.axiom/workflow-toolchain.toml` (`axiom_corpus_ref`), and the corpus commit in
   `.github/workflows/repository-checks.yml` (`axiom-corpus-ref`) and
   `.github/workflows/bulk-encode.yml` (`AXIOM_CORPUS_REF`).
3. The encodings each need a signed-encoder dispatch.
