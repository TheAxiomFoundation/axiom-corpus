# UK indirect-tax ingest reasoning (VAT, fuel duty, TV licence)

Impact basis:

- The PolicyEngine-UK conformance universe (axiom-oracles conformance/uk-pe.yaml,
  release 2.89.2) carried `vat`, `fuel_duty`, and `tv_licence` as in-scope but
  uncovered — PE-UK computes all three but no rulespec module or oracle suite ran.
  Closing them needs the operative statutory rates grounded in the corpus.

Official sources (primary official, legislation.gov.uk CLML XML, expression
current for FY 2026-27; as-of / expression-date 2026-06-30):

- Value Added Tax Act 1994 (c. 23) s.2 "Rate of VAT and determination of value":
  "VAT shall be charged at the rate of 20 per cent". s.29A "Reduced rate":
  supplies of a description specified in Schedule 7A "shall be charged at the rate
  of 5 per cent". Version `2026-07-07-uk-vata-1994`.
- Hydrocarbon Oil Duties Act 1979 (c. 5) s.6 "Excise duty on hydrocarbon oil":
  duty of excise "at the rates specified in subsection (1A)"; the standing s.6(1A)
  rate is "£0.5795 a litre in the case of unleaded petrol" and the same for heavy
  oil (diesel). The temporary 5p fuel duty cut (from 23 March 2022, extended and
  partially unwound by the Autumn Budget 2025) is set by annual Budget resolution
  and is NOT carried into the consolidated s.6(1A) text (verified: s.6(1A) reads
  £0.5795 at expression dates 2024-06-30 and 2026-06-30). Version
  `2026-07-07-uk-hoda-1979`.
- Communications Act 2003 (c. 21) s.363 "Licence required for use of TV receiver"
  and s.365 "TV licence fees": fee liability is "such sum ... as may be provided
  for by ... regulations", "subject to any concession" the BBC provides. Version
  `2026-07-07-uk-communications-tvl`.
- Communications (Television Licensing) Regulations 2004 (SI 2004/692) Schedule 1:
  the colour (including) General Form licence fee is "£180.00" for 2026-27. Version
  `2026-07-07-uk-tvl-regs-2004`.

Encoding: the composed policy pipelines rulespec-uk uk/policies/govuk/{vat,
fuel-duty,tv-licence}.yaml re-inline the operative atoms from these provisions.
The over-75 (100 per cent) and blind (50 per cent) TV concession rates and the
temporary fuel duty reduction are administered / Budget-resolution values not in
the consolidated legislation; they are supplied simulation inputs (matching the
PolicyEngine parameters) rather than corpus-grounded literals.
