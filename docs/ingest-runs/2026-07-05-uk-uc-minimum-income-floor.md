# UK Universal Credit minimum-income-floor threshold ingest reasoning

Impact basis:

- axiom-corpus issue 213 records that Universal Credit Regulations 2013
  (`uksi/2013/376`) **regulation 90** — the individual and couple thresholds
  that define gainful self-employment for the minimum income floor (MIF) — was
  not in the corpus. `rulespec-uk/uk/regulations/uksi/2013/376/62.yaml` encodes
  the MIF deeming logic (reg 62(2)/(3)/(6)/(7)) but reads the threshold amounts
  as free inputs (`individual_threshold_amount_set_out_in_regulation_90_2`,
  `couple_threshold_amount_set_out_in_regulation_90_3`) because reg 90 was
  ungrounded, so the MIF floor could not be computed end to end and the composed
  UC award pipeline (`uk/policies/universal_credit_composed_award_pipeline.yaml`)
  reads a supplied floored `uc_pilot_earned_income_monthly`.
- Reg 90's threshold is not a bare figure: reg 90(2) defines the individual
  threshold as the applicable National Minimum Wage / National Living Wage
  hourly rate (regulation 4 or 4A of the National Minimum Wage Regulations 2015)
  multiplied by an hours figure (16, or the reg 88 "expected number of hours",
  default 35) and converted to a monthly amount (× 52 ÷ 12). Grounding reg 90
  therefore also requires grounding the NMW/NLW hourly-rate source it points to,
  so the derived threshold carries its amount in resolved provision text rather
  than resting on a memorised rate.

Official sources (primary official only), legislation.gov.uk CLML, in-force
expression current for 2026-27 (`--expression-date 2026-04-06`, matching the
existing `2026-06-03-uk-universal-credit` UC source and the 1 April 2026 NMW
uprating):

- **Universal Credit Regulations 2013 (SI 2013/376) regulation 90** "Claimants
  subject to no work-related requirements". Carries the MIF machinery: reg 90(2)
  individual threshold = hourly rate under NMW Regs reg 4 / 4A(1)(a)-(c) for 16
  hours (s.20/s.21 claimants) or the reg 88 expected hours (s.22 claimants),
  × 52 ÷ 12; reg 90(3) couple threshold = the sum of individual thresholds, or
  (single-claim-by-reg-3(3) case) the individual threshold plus 35 hours at the
  reg 4 rate × 52 ÷ 12; reg 90(4) the apprenticeship-contract case at the reg
  4A(1)(d) apprentice rate; reg 90(5) the express link into reg 62 (minimum
  income floor). The reg 90 body captured names regs 4, 4A, 62, 88 and the
  16/35/30-hour figures verbatim.
- **National Minimum Wage Regulations 2015 (SI 2015/621) regulation 4** "The
  rate of the national minimum wage": the single hourly national living wage
  rate **£12.71** (21 and over).
- **National Minimum Wage Regulations 2015 (SI 2015/621) regulation 4A**: the
  age-banded hourly rates — **£10.85** (18 to under 21), **£8.00** (under 18),
  **£8.00** (apprenticeship rate, reg 4A(1)(d)), all in force from 1 April 2026,
  and the reg 4A(2) rule that the apprentice rate displaces the others.

Verification (corrupt-a-digit standard — the amounts are present as amounts in
the resolved provision bodies, not stripped to cross-references):

- reg 4 body: "… ('the national living wage rate') is £12.71."
- reg 4A body: "£10.85 for a worker who is aged 18 years or over (but is not yet
  aged 21 years); £8.00 for a worker who is aged under 18 years; £8.00 for a
  worker to whom the apprenticeship rate applies …".
- reg 90 body: the individual/couple threshold definitions with the reg 4/4A
  hourly-rate cross-references, the 16/35/30-hour multipliers, the × 52 ÷ 12
  monthly conversion, and the reg 62 MIF link.
- The reg 88 expected-hours figure (35) that reg 90(2)(b) points to is already
  grounded in the `2026-06-03-uk-universal-credit` source; this ingest completes
  the chain reg 62 (logic) → reg 90 (threshold definition) → reg 4/4A (hourly
  rate) → reg 88 (expected hours).

Scope:

- `uk/regulation` version `2026-07-05-uk-uc-minimum-income-floor`: three
  provisions (UC Regs reg 90, NMW Regs reg 4, NMW Regs reg 4A) as
  legislation.gov.uk CLML. Coverage complete (3 sources, 3 provisions, 3
  matched, 0 missing, 0 extra).

Citation-path ratchet:

- `schema/citation-path.v1.json` `known_irregulars_ratchet.uppercase_segments`
  raised 1346 → 1347 for the single new uppercase-suffixed provision number
  `uk/regulation/uksi/2015/621/4A` — a genuine legislation.gov.uk provision
  form (as with `24A`, `80C`, `681B`), reviewed and bumped via
  `--update-baselines`.

Source-XML storage (R2 only):

- The three legislation.gov.uk CLML source XML files
  (`data/corpus/sources/uk/regulation/2026-07-05-uk-uc-minimum-income-floor/…`)
  are R2-backed provenance and are intentionally NOT committed to git (a scoped
  `.gitignore` rule excludes them). They embed upstream `EffectId="key-<hex>"`
  CLML effect identifiers that GitHub org-level push protection false-positives
  as Mailgun API keys (11 across the three files). The normalized provisions in
  `data/corpus/provisions/uk/regulation/2026-07-05-uk-uc-minimum-income-floor.jsonl`
  carry the verbatim statutory text (the parser strips these commentary IDs),
  and the signed ingest manifest records the source-XML sha256 hashes, so the R2
  provenance chain and the guard remain intact. This matches the Scottish income
  tax (#216) and HICBC (#221) ingest precedents.

Not grounded (honestly):

- The Local Housing Allowance / actual NMW uprating order provenance beyond
  regs 4/4A is out of scope; reg 4/4A already carry the live figures the reg 90
  threshold multiplies. The reg 88 expected-hours source is already in the
  corpus and is not re-ingested here.
