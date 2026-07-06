# UK passported maternity/food grants ingest reasoning

Impact basis:

- UKMOD wave 2, lane E covers the three passported grants held out of wave 1:
  Sure Start Maternity Grant (`bmamt_uk`, already grounded via
  `uk/regulation/uksi/2005/3061/5`), Healthy Start (`bmamt01_uk`), and Best Start
  Foods (`bmascmt01_uk`). Healthy Start and Best Start Foods were not in the
  corpus, so the rulespec-uk passported-grant oracle pipelines could not ground
  their weekly rates end to end. All three are deterministic passported surfaces
  (eligibility passports off a qualifying means-tested benefit in payment, e.g.
  Universal Credit `bsauc_s > 0`); unlike the excluded Best Start Grant
  (`bmascmt_uk`), neither consumes UKMOD's stochastic `i_rand_tu` take-up draw.

Official sources (primary official only), legislation.gov.uk CLML, in-force
expression current for 2026-27 (`--expression-date 2026-04-06`):

- **Welfare Foods (Best Start Foods) (Scotland) Regulations 2019 (SSI 2019/193)
  regulation 13** "Value of benefit". Fixes the basic rate at **£5.60 for each
  week** (regulation 13(1), as substituted for £5.40 by the Social Security
  (Up-rating) (Miscellaneous Amendments) (Scotland) Regulations 2026, SSI
  2026/170, with effect from 1 April 2026), and **double the basic rate**
  (£11.20 for each week) while the child has not yet reached the age of one,
  reverting to the basic rate from age one until the child reaches the age of
  three. The reg 13 body captures £5.60 and "double the basic rate" verbatim.
- **Healthy Start Scheme and Welfare Food (Amendment) Regulations 2005 (SI
  2005/3262) regulation 8**. The value represented by a voucher or credit "must
  not be less than **£3.10**", and "the Secretary of State may increase or
  decrease the voucher or credit value". The operative weekly amount (£4.25 per
  eligible individual, doubled to £8.50 for a child under one, in force to 31
  March 2026; UKMOD UK_2026's `$HSFood`) is a determination above that floor,
  not a figure fixed in the regulation, so the rulespec-uk pilot supplies it as
  an input and floors it at the grounded £3.10 minimum.

Source-XML handling:

- Both the Best Start Foods reg 13 and Healthy Start reg 8 CLML source XML embed
  upstream `key-...` commentary identifiers that GitHub org push protection
  false-positives as Mailgun keys, so both are R2-backed provenance only
  (gitignored). Their normalized provisions carry the verbatim statutory text
  and are committed; the signed ingest manifests record the source-XML sha256
  hashes.

Commands:

    uv run --extra dev axiom-corpus-ingest extract-uk-legislation \
      --base data/corpus --version 2026-07-06-uk-best-start-foods-reg13 \
      --source clml --citation ssi/2019/193/regulation/13 \
      --source-as-of 2026-07-06 --expression-date 2026-04-06

    uv run --extra dev axiom-corpus-ingest extract-uk-legislation \
      --base data/corpus --version 2026-07-06-uk-healthy-start-reg8 \
      --source clml --citation uksi/2005/3262/regulation/8 \
      --source-as-of 2026-07-06 --expression-date 2026-04-06
