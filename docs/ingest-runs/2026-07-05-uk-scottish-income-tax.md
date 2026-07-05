# UK Scottish income tax ingest reasoning

Impact basis:

- axiom-corpus issue 214 records that Scottish income tax (non-savings,
  non-dividend income) for tax year 2026-27 cannot be encoded in
  `rulespec-uk` because the corpus carried no Scottish rate law: only ITA
  2007 s.10 (which references s.11A) and s.16 (which mentions "Scottish
  taxpayer") were grounded. The UKMOD-parity earnings sweep against
  `UKMOD_PUBLIC_B2026.03` `UK_2026` needs a Scottish-resident case, but every
  Scottish band/rate value was ungrounded.

Official sources (primary official only):

- Income Tax Act 2007 (c. 3) s.11A "Income charged at Scottish rates",
  legislation.gov.uk CLML XML, expression current for 2026-27
  (dct:valid 2026-04-06). Charging text: "Income tax is charged at Scottish
  rates on the non-savings income of a Scottish taxpayer." s.11A(1A) was
  substituted for s.11A(1)-(3) (30.11.2016, effect for 2017-18 onward) by the
  Scotland Act 2016.
- Scotland Act 1998 (c. 46) s.80C "Power to set Scottish rates for Scottish
  taxpayers", legislation.gov.uk CLML XML, current expression
  (dct:valid 2026-06-30). This is the rate/band-setting machinery: "The
  Scottish Parliament may by resolution (a 'Scottish rate resolution') set
  the Scottish basic rate, and any other rates, for the purposes of section
  11A of the Income Tax Act 2007". Where an SRR sets more than one rate it
  must set limits to determine which rate applies.
- Scotland Act 2016 (c. 11) s.13 "Power of Scottish Parliament to set rates
  of income tax", legislation.gov.uk CLML XML. The amending provision that
  rewrote Scotland Act 1998 s.80C into its current form (substituting the
  s.80C(1) power to reference ITA 2007 s.11A) and, by ss.13(14)/14, omitted
  ITA 2007 s.6A (which formerly held the Scottish basic/higher/additional
  rate machinery). Grounds the devolution provenance of the current power.
- Scottish Government, "Scottish Rate Resolution 2026 to 2027 - draft motion
  and explanatory note", gov.scot official publication, published
  2026-01-13; the motion in these terms was debated and agreed by the
  Scottish Parliament on 2026-02-19. Draft-motion page carries the verbatim
  rate/band table under section 80C of the Scotland Act 1998, for the
  non-savings non-dividend income of a Scottish taxpayer for 2026-27:
  starter 19% to £3,967; basic 20% £3,967-£16,956; intermediate 21%
  £16,956-£31,092; higher 42% £31,092-£62,430; advanced 45%
  £62,430-£125,140; top 48% above £125,140.

Verification:

- The SRR motion text explicitly cites "section 11A of the Income Tax Act
  2007", cross-linking the money atoms (bands + rates) to the charging
  section and the s.80C power ingested here. All six band figures are quoted
  verbatim from the gov.scot draft-motion page (block-1).
- Reserved/devolved split confirmed from the sources: Scottish rates apply
  only to non-savings non-dividend income (ITA 2007 s.11A + s.16); savings
  and dividend income remain at UK rates; the personal allowance is UK-wide
  and is not set by the SRR (the motion charges the bands "above the personal
  allowance").

Scope:

- `uk/statute` version `2026-07-05-uk-scottish-income-tax`: three provisions
  (ITA 2007 s.11A, Scotland Act 1998 s.80C, Scotland Act 2016 s.13) as
  legislation.gov.uk CLML.
- `uk/guidance` version `2026-07-05-uk-scottish-income-tax`: the gov.scot
  Scottish Rate Resolution 2026-27 draft motion, with block-1 carrying the
  verbatim rate/band table.

Source-XML storage (R2 only):

- The three legislation.gov.uk CLML source XML files
  (`data/corpus/sources/uk/statute/2026-07-05-uk-scottish-income-tax/...`)
  are R2-backed provenance and are intentionally NOT committed to git (a
  scoped `.gitignore` rule excludes them). They embed upstream
  `EffectId="key-<32 hex>"` CLML commentary/effect identifiers that GitHub
  org-level push protection false-positives as Mailgun API keys (the same
  identifiers appear in ~8,700 already-committed UK source XML rows that
  predate the org push-protection rule). The normalized provisions in
  `data/corpus/provisions/uk/statute/2026-07-05-uk-scottish-income-tax.jsonl`
  carry the verbatim statutory text (the parser strips these commentary IDs),
  and the signed ingest manifest records the source-XML sha256 hashes, so the
  R2 provenance chain and the guard remain intact. Per README, R2 is the store
  for raw XML/PDF; the git copy is a mirror convenience. The gov.scot SRR
  guidance HTML source is committed normally (no tripping tokens).

Dropped, honestly:

- ITA 2007 s.6A "The Scottish basic, higher and additional rates" is NOT
  grounded. Issue 214 suggested it "as enacted/amended", but the Scotland
  Act 2016 (s.13(14)/14) OMITTED s.6A with effect for 2017-18 onward, so its
  current expression is an empty (ellipsis) body carrying no verifiable text
  or money atom. The live rate machinery it once held is fully covered by the
  s.80C power + the s.11A charging section + the s.13 amendment (whose
  captured body records the omission), so grounding an empty s.6A would add
  identity noise without grounding value.
