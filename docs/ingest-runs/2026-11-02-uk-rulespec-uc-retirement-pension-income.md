# uk-rulespec-2026-11-02-uc-retirement-pension-income: release selector

Date: 2026-11-02. Selector
`manifests/releases/uk-rulespec-2026-11-02-uc-retirement-pension-income.json`, built by
`scripts/repro/uk_rulespec_2026_11_02_uc_retirement_pension_income.py` and checked by
`tests/test_uk_rulespec_2026_11_02_uc_retirement_pension_income.py`.

## What it selects

rulespec-uk's corpus pin, `uk-rulespec-2026-10-25-pe-child-definitions` (193 scopes;
rulespec-uk `.axiom/toolchain.toml` on `main` 0497350d74), plus exactly two scopes. Both
carry signed ingest manifests and lock files, and `manifests/withdrawn-scopes.yaml` lists neither:

| Scope | Provisions | Ingested |
| --- | --- | --- |
| `uk/statute/2026-11-02-uk-uc-retirement-pension-income` | SPCA 2002 s.16 | `docs/ingest-runs/2026-11-02-uk-uc-retirement-pension-income.md` |
| `uk/regulation/2026-11-02-uk-uc-retirement-pension-income` | UC Regs 2013 regs 67 and 73; SPC Regs 2002 reg 16 | the same run note |

That makes 195 scopes, a strict superset of the pin. The scopes let the supervised encoder state
what retirement pension income Universal Credit counts as unearned income
(TheAxiomFoundation/rulespec-uk#385).

## Paths

A re-pin changes no existing resolution. The two scopes hold four citation paths, and none of the
pin's 193 scopes carries any of them (checked against every pin scope's provision file, 21,792
rows). The selector keeps the pin's quality profile, `complete-expression-dates-v1`, under which
`validate-release` requires every citation path to be unique across the release.

The pin selects no withdrawn scope, and neither do the additions, so this selector needs no
withdrawn-scope exception.

## Checks

- The reproducer matches the committed selector byte for byte.
- The selector equals the pin plus the two scopes, sorted. Each added scope is locked and not
  withdrawn.
- A Hypothesis property checks the build rule over arbitrary bases, including bases that already
  hold either addition.
- `axiom-corpus-ingest validate-release` with corpus data on this selector: `ok`, 0 errors and
  0 warnings. It reports one notice, the baselined `navigation_body` finding of
  `uk-broxtowe/manual/2026-09-05-broxtowe-council-tax-reduction-2026-2027`, which the pin already
  carries.
- CI's `Validate named release selectors` job repeats the deep validation.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`. **Publish only. Do not activate it.** It
   serves as a pin release for rulespec-uk; see `docs/named-release-publication.md`.
2. Re-pin rulespec-uk to this release. Four files name the corpus: `.axiom/toolchain.toml`
   (`axiom_corpus_release` and `axiom_corpus_release_content_sha256`),
   `.axiom/workflow-toolchain.toml` (`axiom_corpus_ref`), and the corpus commit in
   `.github/workflows/repository-checks.yml` (`axiom-corpus-ref`) and
   `.github/workflows/bulk-encode.yml` (`AXIOM_CORPUS_REF`).
3. Encode s.16 and reg 67, and re-encode reg 66, each through a signed-encoder dispatch.
