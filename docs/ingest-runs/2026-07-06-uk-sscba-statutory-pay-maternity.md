# UK statutory-pay and maternity stack ingest reasoning (SMP, MA, SPP)

Impact basis:

- axiom-oracles conformance `conformance/detail/uk.json` marks the UKMOD
  statutory-pay/maternity policies `bmact_uk` (Statutory Maternity Pay),
  `bmanc_uk` (Maternity Allowance), and `bpact_uk` (Statutory Paternity Pay) as
  in-scope but uncovered: Axiom has no SMP/MA/SPP suite and rulespec-uk does not
  encode them. This ingest grounds the governing primary statute so the three
  entitlements can be encoded as corpus-grounded money atoms and compared to
  the live UKMOD UK_2026 outputs `bmact_s` / `bmanc_s` / `bpact_s`.
- Empirically confirmed against UKMOD_PUBLIC_B2026.03 / UK_2026 that all three
  policies carry `<Switch>on</Switch>` and compute from ordinary demographic /
  earnings inputs on synthetic HHoT cases (SMP from `yem`, MA from `yem`+`yse`
  gated on `bmact_s = 0`, SPP from `yem`), resolving the Country-Report "not
  simulated in the baseline" note (the FRS baseline does not populate maternity
  spells; the policy still computes).

Official sources (primary official only), legislation.gov.uk CLML XML, in-force
expression current for 2026-27 (requested at `--expression-date 2026-04-06`),
Social Security Contributions and Benefits Act 1992 (c. 4):

## Statutory Maternity Pay — Part XII (`2026-07-06-uk-sscba-smp`)

- s.164 "Statutory maternity pay — entitlement and liability to pay" — the
  entitlement section. A woman is entitled to SMP if she has been in employed
  earner's employment for a continuous period of at least 26 weeks ending with
  the qualifying week, her normal weekly earnings are not less than the lower
  earnings limit, she has ceased to work, and pregnancy has reached (or she has
  been confined before) the 11th week before the expected week of confinement.
  Grounds the lower-earnings-limit and continuous-employment conditions that the
  UKMOD `bmact_uk` eligibility mirrors (`(dgn=0) & IsParentOfDepChild & (yem >
  $SMPlel) & (liwwh>6)`).
- s.165 "The maternity pay period" — the period for which SMP is payable is up
  to 39 weeks. Grounds the 39-week duration cap (`i_durweeks_bmact` capped at
  39 in `bmact_uk`).
- s.166 "Rates of payment" — SMP is payable at the earnings-related rate (90% of
  normal weekly earnings) for the first 6 weeks and the prescribed (flat) weekly
  rate, or 90% of normal weekly earnings if lower, for the remaining weeks.
  Grounds the two-limb 90%/flat-rate structure (`$SMPrr` 90% earnings-related
  rate for the first six weeks; `$SMPwsr` prescribed weekly standard rate
  thereafter, subject to the 90% floor) that `bmact_uk`'s BenCalc encodes.
- s.171 "Interpretation of Part XII etc." — defines "confinement", "the
  qualifying week", "normal weekly earnings", "employed earner's employment"
  for the Part. Grounds the normal-weekly-earnings base (UKMOD
  `i_yempv_bmact = max(yivwg*(lhw*52/12), yem)`).

The prescribed weekly standard rate and the lower earnings limit are set by
regulations and the annual re-rating order (delegated by ss.166/171), not by
the primary Act; the ingested Act text grounds the *structure* (90% rate, flat
rate, 39-week period, LEL condition). The in-force numeric rates are sourced
from the UKMOD parameterisation ($SMPwsr, $SMPrr, $SMPlel) and are cited on the
encode side as the oracle parameter source, not invented.

## Maternity Allowance — Part II, s.35/35A/35B (`2026-07-06-uk-sscba-maternity-allowance`)

- s.35 "State maternity allowance" — a woman is entitled to a maternity
  allowance if she has been engaged in employment (employed or self-employed)
  for at least 26 of the 66 weeks before the expected week of confinement, her
  average weekly earnings are not less than the maternity allowance threshold,
  and she is not entitled to statutory maternity pay for the same week. Grounds
  the UKMOD `bmanc_uk` conditions: female parent, `bmact_s = 0` (no SMP),
  earnings (employment or self-employment) above the MA threshold `$SMAThresh1`,
  and the 26-of-66-weeks test (`liwwh > 22/66*12`).
- s.35A "Appropriate weekly rate of maternity allowance" — the rate is the
  lesser of the prescribed standard rate and 90% of the woman's average weekly
  earnings, for up to 39 weeks. Grounds the MA rate limb (UKMOD reuses the SMP
  `$SMPwsr`/`$SMPrr` structure: 90% of average weekly earnings vs the standard
  weekly rate).
- s.35B "State maternity allowance for participating wife or civil partner of
  self-employed earner" — the lower-rate MA for the participating spouse of a
  self-employed earner. Grounds the self-employment MA base that makes a
  self-employed mother (yse>0, yem=0, hence bmact_s=0) MA-eligible.

## Statutory Paternity Pay — Part 12ZA, ss.171ZA–171ZJ (`2026-07-06-uk-sscba-statutory-paternity-pay`)

- s.171ZA "Entitlement: birth" — a person is entitled to statutory paternity
  pay if they satisfy the conditions as to the relationship with the child and
  the mother, have been in employed earner's employment for a continuous period
  of at least 26 weeks, and have normal weekly earnings not less than the lower
  earnings limit. Grounds the UKMOD `bpact_uk` eligibility (eligible parent with
  qualifying previous earnings `i_yempv_bpact`).
- s.171ZB "Entitlement: adoption" — the adoption limb of the entitlement.
- s.171ZE "Rate and period of pay" — SPP is payable at the prescribed weekly
  rate, or 90% of normal weekly earnings if lower, for the statutory paternity
  pay period (up to 2 weeks). Grounds the SPP rate/period (`$SMPwsr` weekly rate
  capped at the 2-week period) that `bpact_uk` encodes.
- s.171ZJ "Part 12ZA: supplementary" — interpretation and normal-weekly-earnings
  definition for the Part. Grounds the SPP normal-weekly-earnings base.

Verification:

- The ingested Act text grounds the entitlement conditions and rate *structure*
  of all three benefits. The in-force numeric rates ($SMPwsr prescribed weekly
  standard rate, $SMPrr 90% earnings-related rate, $SMPlel lower earnings limit,
  $SMAThresh1 maternity-allowance threshold) are set by delegated regulations
  and the annual re-rating order; they are taken verbatim from the UKMOD UK_2026
  parameterisation and cited on the encode side as the oracle parameter source
  (never invented). Each encoded money atom traces to either the ingested
  provision text (structure) or the named UKMOD constant (in-force value).

Scope:

- `uk/statute` version `2026-07-06-uk-sscba-smp`: 4 provisions (SSCBA 1992
  ss.164, 165, 166, 171). Coverage complete (4 sources, 4 provisions, 4 matched).
- `uk/statute` version `2026-07-06-uk-sscba-maternity-allowance`: 3 provisions
  (ss.35, 35A, 35B). Coverage complete (3 sources, 3 provisions, 3 matched).
- `uk/statute` version `2026-07-06-uk-sscba-statutory-paternity-pay`: 4
  provisions (ss.171ZA, 171ZB, 171ZE, 171ZJ). Coverage complete (4 sources, 4
  provisions, 4 matched).

Source-XML storage (R2 only):

- The legislation.gov.uk CLML source XML files under
  `data/corpus/sources/uk/statute/2026-07-06-uk-sscba-*/` are R2-backed
  provenance and are intentionally NOT committed to git (scoped `.gitignore`
  rules exclude them, alongside the blanket `data/` rule). They embed upstream
  `EffectId="key-<hex>"` CLML commentary identifiers that GitHub org-level push
  protection false-positives as Mailgun API keys — the same pattern handled for
  the Scottish income tax and HICBC ingests. The normalized provisions carry the
  verbatim statutory text (the parser strips the commentary IDs), and the signed
  ingest manifests record the source-XML sha256 hashes, so the R2 provenance
  chain and the ingested-artifact guard remain intact.
