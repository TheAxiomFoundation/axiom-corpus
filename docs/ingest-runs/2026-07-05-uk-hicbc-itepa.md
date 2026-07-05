# UK High Income Child Benefit Charge (HICBC) ingest reasoning

Impact basis:

- rulespec-uk issue 75 records that the composed Child Benefit oracle pipeline
  (`uk/statutes/child_benefit/pilot_child_benefit_oracle_pipeline.yaml`, merged
  in rulespec-uk#76) encodes only the Social Security Contributions and Benefits
  Act 1992 s.141 gross entitlement with the SI 2006/965 reg.2 weekly rates. It
  deliberately does not encode the High Income Child Benefit Charge, because the
  charge provisions were not in the corpus: the £60,000 threshold and the
  1%-per-£200 taper could not be encoded as corpus-grounded money atoms, so the
  UKMOD oracle comparison ran gross-to-gross (Axiom gross vs UKMOD `bch_s +
  bchrd_s`, adding back UKMOD's separately-reported clawback). This ingest
  grounds the charge so a net-of-charge surface can be encoded and compared to
  UKMOD `bch_s` directly.

Official sources (primary official only), legislation.gov.uk CLML XML, in-force
expression current for 2026-27 (each provision's `dct:valid` 2026-07-01,
requested at `--expression-date 2026-04-06`), Income Tax (Earnings and Pensions)
Act 2003 (c. 1) Part 10 Chapter 8 "High income child benefit charge":

- s.681B "High income child benefit charge" — the charging section. P is liable
  to a charge to income tax for a tax year if P's adjusted net income for the
  year exceeds £60,000 and one or both of conditions A and B are met. Condition
  A: P (or no partner with higher adjusted net income) is entitled to child
  benefit for a week in the tax year. Condition B: P's partner Q is entitled and
  P has the higher adjusted net income. Grounds the £60,000 threshold money atom.
- s.681C "The amount of the charge" — the amount is the appropriate percentage of
  the child benefit amounts to which conditions A/B relate. The appropriate
  percentage is 100%, or if less, the percentage from the formula (ANI − L) / X
  %, where L is £60,000 and X is £200. Amounts and the percentage are rounded
  down to the nearest whole number. Grounds the taper (1% per £200 over £60,000),
  the 100% cap (hence full clawback at £60,000 + 100 × £200 = £80,000), the
  L=£60,000 and X=£200 money atoms, and the round-down rule.
- s.681D "Extension of charge in cases where child not living with claimant" —
  applies the charge where a contributor (SSCBA 1992 s.143(1)(b)) is entitled but
  the child lives with another person.
- s.681E "Special cases" — the disregards. Amounts under a s.13A Social Security
  Administration Act 1992 election (election for payment of child benefit not to
  be made if the charge would be triggered) are disregarded for the Chapter, as
  are s.145A SSCBA 1992 post-death amounts. Grounds the elect-out disregard.
- s.681F "Alteration of income limit etc by Treasury order" — the Treasury may by
  order substitute L (in s.681B(1)(a) / s.681C(2)) or X (in s.681C(2)); grounds
  that the £60,000 and £200 atoms are the in-force values pending any such order.
- s.681G "Meaning of 'partner'" — married/civil partners not separated, or living
  together as if a married couple or civil partners. Grounds the partner test
  that conditions A/B in s.681B depend on.
- s.681H "Other interpretation provisions" — "adjusted net income" of a person
  for a tax year means adjusted net income as determined under s.58 of ITA 2007;
  "week" means 7 days beginning with a Monday. Grounds the adjusted-net-income
  base cross-reference and the weekly period.

Verification:

- Every money atom is quoted verbatim from the ingested provision text: the
  £60,000 threshold (s.681B(1)(a), and "L" in s.681C(2)), the £200 taper step
  ("X" in s.681C(2)), the 100% appropriate-percentage cap and the round-down rule
  (s.681C(2)-(3)). The full-clawback point of £80,000 is not a separate atom: it
  is the income at which (ANI − 60,000) / 200 reaches 100, i.e. 60,000 + 100 ×
  200, and is derived from the s.681C(2) formula and cap.
- The adjusted-net-income base is a cross-reference (s.681H(2) → ITA 2007 s.58),
  not a HICBC money atom; the encode cites s.681H(2) for the base.
- Provenance of the Chapter: Part 10 Chapter 8 was inserted (with effect per Sch.
  1 para. 7 of the amending Act) by Finance Act 2012 (c. 14) Sch. 1 para. 1; the
  £60,000 / £80,000 numbers are the values in force after the Finance Act 2024
  threshold change (this is the current in-force expression, so the raised
  threshold and £200 step are what the CLML returns, not the historic
  £50,000/£60,000/£100 parameters).

Scope:

- `uk/statute` version `2026-07-05-uk-hicbc-itepa`: seven provisions (ITEPA 2003
  ss.681B, 681C, 681D, 681E, 681F, 681G, 681H) as legislation.gov.uk CLML.
  Coverage complete (7 sources, 7 provisions, 7 matched, 0 missing, 0 extra).

Source-XML storage (R2 only):

- The seven legislation.gov.uk CLML source XML files
  (`data/corpus/sources/uk/statute/2026-07-05-uk-hicbc-itepa/ukpga/2003/1/...`)
  are R2-backed provenance and are intentionally NOT committed to git (a scoped
  `.gitignore` rule excludes them, alongside the blanket `data/` rule). They
  embed upstream `EffectId="key-<32 hex>"` CLML commentary/effect identifiers
  (56 across the seven files) that GitHub org-level push protection
  false-positives as Mailgun API keys — the same pattern handled for the
  Scottish income tax ingest. The normalized provisions in
  `data/corpus/provisions/uk/statute/2026-07-05-uk-hicbc-itepa.jsonl` carry the
  verbatim statutory text (the parser strips these commentary IDs), and the
  signed ingest manifest records the source-XML sha256 hashes, so the R2
  provenance chain and the ingested-artifact guard remain intact. Per README, R2
  is the store for raw XML/PDF; the git copy is a mirror convenience.
