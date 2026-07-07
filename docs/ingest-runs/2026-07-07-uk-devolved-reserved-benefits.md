# UK devolved/reserved benefit ingest reasoning (CWHA, Scottish Carer Supplement, contribution-based JSA)

Impact basis:

- The PolicyEngine-UK / UKMOD UK_2026 conformance universe carries three
  benefit amounts held out of the earlier UK benefit-rate ingests: the Scottish
  Child Winter Heating Payment (`bchht`), the Scottish Carer Supplement /
  Carer's Allowance Supplement (`bcrdicm`), and contribution-based / New Style
  Jobseeker's Allowance (`bunct`). Closing them needs the operative statutory
  amounts grounded in the corpus so the rulespec-uk policy pipelines can cite
  them via proof atoms.

Official sources (primary official, legislation.gov.uk CLML XML, expression
current for FY 2026-27; source-as-of / expression-date 2026-06-30):

- Winter Heating Assistance for Children and Young People (Scotland) Regulations
  2020 (SSI 2020/352), renamed the Child Winter Heating Payment Regulations:
  - regulation 10 "Value and form of child winter heating assistance": "the
    value of child winter heating assistance is £265.50" (2026-27 value, uprated
    by SSI 2026/170; reg. 10's consolidated expression carries the figure with no
    outstanding effects). Corpus path `uk/regulation/ssi/2020/352/10`.
  - regulation 4 "Entitlement to child winter heating assistance": entitlement of
    a "child or young person" who is "entitled to receive payment of ... the
    highest rate of the care component of ... Disability Living Allowance" (or the
    enhanced daily living component of PIP / equivalent) in a qualifying week.
    Corpus path `uk/regulation/ssi/2020/352/4`.
- Social Security (Scotland) Act 2018 (asp 9) section 81 "Carer's allowance
  supplement": the statutory basis — the Scottish Ministers "must make a payment
  (a 'carer's allowance supplement')" for each of the two periods 1 April to 30
  September and 1 October to 31 March of each financial year, calculated by a
  formula with an annual CPI uprating duty; no fixed cash amount is stated in the
  Act. Corpus path `uk/statute/asp/2018/9/81`.
- Carer's Assistance (Carer Support Payment) (Scotland) Regulations 2023
  (SSI 2023/302) regulation 16 "Weekly rate of payment": "The weekly rate of
  payment of Scottish Carer Supplement is £11.70" (and Carer Support Payment
  £86.45). The weekly Scottish Carer Supplement is the successor to and holds
  ~equal annual value with the twice-yearly Carer's Allowance Supplement. Corpus
  path `uk/regulation/ssi/2023/302/16`.
- Jobseekers Act 1995 (c. 18) section 4 "Amount payable by way of a jobseeker's
  allowance": for a contribution-based JSA, the "personal rate" is calculated by
  "determining the age-related amount applicable" (with prescribed deductions);
  the age-related amount "shall be determined in [the prescribed manner]" —
  i.e. delegated to the JSA Regulations. Corpus path `uk/statute/ukpga/1995/18/4`.
- Jobseeker's Allowance Regulations 1996 (SI 1996/207) regulation 79 "Weekly
  amounts of contribution-based jobseeker's allowance": the age-related amount
  "for the purposes of section 4(1)(a)" is "in the case of a person who has not
  attained the age of 25, £75.65 per week" and "in the case of a person who has
  attained the age of 25, £95.55 per week" (2026-27 values). Corpus path
  `uk/regulation/uksi/1996/207/79`.
- Social Security Benefits Up-rating Order 2026 (SI 2026/148) article 25
  "Increase in age-related amounts of contribution-based Jobseeker's Allowance":
  in regulation 79(1) of the JSA Regulations 1996, in sub-paragraph (a) for
  "£72.90" substitute "£75.65" and in sub-paragraph (c) for "£92.05" substitute
  "£95.55" — the 2026-27 uprating provenance. Corpus path
  `uk/regulation/uksi/2026/148/article/25`.

Provenance handling: the normalized provisions (with the verbatim statutory
amounts) plus the inventory and coverage artifacts are committed; the raw CLML
source XML snapshots are R2-backed provenance only (they embed upstream `key-...`
commentary identifiers that GitHub org push protection false-positives as Mailgun
keys) and are gitignored — the signed ingest manifests record the source-XML
sha256 hashes.

Encoding: the composed rulespec-uk policy pipelines
uk/policies/govuk/{child-winter-heating-payment,scottish-carer-supplement,
contribution-based-jsa}.yaml ground their statutory amounts on these provisions,
importing the flat/age-banded regulation amounts and gating on Scotland residence
(CWHA, Scottish Carer Supplement), the DLA/PIP disability passport (CWHA), and
Carer's Allowance receipt (Scottish Carer Supplement). The passport and receipt
qualifiers are supplied simulation inputs for the UKMOD UK_2026 oracle grid rather
than re-derived here.
