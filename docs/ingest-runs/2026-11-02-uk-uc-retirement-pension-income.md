# UK retirement pension income for Universal Credit unearned income

Date: 2026-11-02. Branch `ingest/uk-uc-retirement-pension-income`, cut from
`origin/main` dbb59ff6a.

Universal Credit Regulations 2013 reg 66(1)(a) counts "retirement
pension income (see regulation 67)" as unearned income. Reg 67 gives that
phrase the meaning in State Pension Credit Act 2002 s.16, as extended by State
Pension Credit Regulations 2002 reg 16. rulespec-uk takes the classification as
an opaque input in reg 66 because its corpus pin,
`uk-rulespec-2026-10-25-pe-child-definitions` (rulespec-uk
`.axiom/toolchain.toml` on `main` 0497350d74), carries none of these
provisions. This ingest supplies them, so the
supervised encoder can encode s.16 and reg 67 and re-encode reg 66 to import
them (TheAxiomFoundation/rulespec-uk#385). PolicyEngine/policyengine-uk#1943
made the matching PolicyEngine fix: it adds State Pension to UC unearned income.

It also captures UC Regs 2013 reg 73 (monthly equivalents of unearned income),
which the rulespec-uk issue names as an optional module.

Reg 67, reg 73 and SPC Regs reg 16 already sit in `2026-06-01-uk-frs-microsim`.
That scope's rows carry the scope name as their `expression_date`, so it cannot
join a `complete-expression-dates-v1` release, and no UK release selects it.
s.16 sits in no scope.

No publication, Supabase load, release selector, activation or registration
step ran here. I signed and locked the scopes in a separate commit after the
clean commit that adds this note.

## Commands

Both runs fetched the current revised text from legislation.gov.uk CLML on
2026-11-02, under version `2026-11-02-uk-uc-retirement-pension-income`.

Statute scope (1 provision):

```bash
uv run --extra dev axiom-corpus-ingest extract-uk-legislation --base data/corpus \
  --version 2026-11-02-uk-uc-retirement-pension-income --source clml \
  --citation ukpga/2002/16/section/16 \
  --source-as-of 2026-11-02 --expression-date 2026-04-06
```

Regulation scope (3 provisions):

```bash
uv run --extra dev axiom-corpus-ingest extract-uk-legislation --base data/corpus \
  --version 2026-11-02-uk-uc-retirement-pension-income --source clml \
  --citation uksi/2013/376/regulation/67 --citation uksi/2013/376/regulation/73 \
  --citation uksi/2002/1792/regulation/16 \
  --source-as-of 2026-11-02 --expression-date 2026-04-06
```

Both runs reported `coverage_complete: true`, 0 missing and 0 extra (statute
1/1, regulation 3/3).

| Citation path | Source | Source SHA256 |
| --- | --- | --- |
| `uk/statute/ukpga/2002/16/16` | `ukpga/2002/16/section/16` | `84311448…` |
| `uk/regulation/uksi/2013/376/67` | `uksi/2013/376/regulation/67` | `72bcd0b6…` |
| `uk/regulation/uksi/2013/376/73` | `uksi/2013/376/regulation/73` | `d8afb040…` |
| `uk/regulation/uksi/2002/1792/16` | `uksi/2002/1792/regulation/16` | `fa0a84ef…` |

Provision files (sha256):

- `data/corpus/provisions/uk/statute/2026-11-02-uk-uc-retirement-pension-income.jsonl`
  `fa17e0670c6e11514f6eb1deeac8fd3c66de2e7345e0ef1888a20fe567c41504` (1 row)
- `data/corpus/provisions/uk/regulation/2026-11-02-uk-uc-retirement-pension-income.jsonl`
  `32ad32158b4d41b9144a0ca843f8bdd60c6cc345e24ab14a2ab7a1137306b5c7` (3 rows)

## Expression date

The rows carry `expression_date` 2026-04-06, the start of the 2026-27 benefit
and tax year, as `2026-09-28-uk-pe-child-definitions` does. Before choosing it
I read the `RestrictStartDate` of every element inside each capture's `Body`,
leaving out the enclosing `Part`, `Chapter` and `Pblock` containers, which carry
instrument-wide dates. No element carries `Status="Prospective"` or a
`RestrictEndDate`. The latest start date in each provision falls on or before
2026-04-06, so the fetched text matches the text in force on that date:

| Provision | Latest element start | `dct:valid` of the capture |
| --- | --- | --- |
| SPCA 2002 s.16 | 2016-04-06 | 2026-07-01 |
| UC Regs 2013 reg 67 | 2013-04-29 | 2026-10-30 |
| UC Regs 2013 reg 73 | 2014-11-26 | 2026-10-30 |
| SPC Regs 2002 reg 16 | 2005-12-18 | 2026-07-16 |

## What an encoder should know

- **s.16(1)(za)** (a state pension under Part 1 of the Pensions Act 2014):
  Pensions Act 2014 s.56(4), Sch 12 para 44, inserted it from 6.4.2016, and
  Sch 11 para 15 substituted (b) on the same date, per the capture's
  commentaries. The row holds only the current text, so the 2016-04-06 start
  of (za) comes from those commentaries.
- **s.16(1)(k) to (n)** appear in the Act's row because legislation.gov.uk
  consolidates SPC Regs reg 16 into s.16. The two rows word (k) differently.
  The Act's (k) reads "section 5 of the Civil List Act 1837 or section 7 of the
  Civil List Act 1952", which the Sovereign Grant Act 2011, Sch 1 para 32,
  substituted from 1.4.2012. Reg 16's own row still lists the five Civil List
  Acts. Each row holds its instrument's current revised text.
- **SPC Regs reg 16** has an empty `extent`. Its capture carries no
  `RestrictExtent` attribute, and neither does the capture of reg 4A of the
  same instrument in `2026-09-28-uk-pe-child-definitions`.
- **Reg 73(3)** holds a MathML fraction, which the row renders in place as
  `N × ( M × 12 365 )`: twelve over three hundred and sixty-five.
- Each row holds the whole provision under the heading "Section 16" or
  "Regulation N". The rows carry no marginal notes, footnotes or annotations,
  and the bodies omit paragraph numbers.

## Validation

- `extract-uk-legislation`: coverage complete for both classes.
- `scripts/validate_citation_paths.py`, with every locked provision file
  fetched: `RESULT: OK`. No baseline moved: all four paths are numeric.
- None of the four citation paths appears in any of the 193 scopes of
  `uk-rulespec-2026-10-25-pe-child-definitions` (21,792 rows scanned). Among
  other UK scopes, only `2026-06-01-uk-frs-microsim` carries reg 67, reg 73 and
  SPC Regs reg 16.
- `validate-release` on scratch one-scope selectors for each class: `ok: true`,
  0 errors, 0 warnings.
- `validate-release` on an uncommitted draft selector (the current UK pin plus
  both new scopes, profile `complete-expression-dates-v1`, 195 scopes):
  `ok: true`, 0 errors, 0 warnings, and one notice, the baselined
  `navigation_body` finding of
  `uk-broxtowe/manual/2026-09-05-broxtowe-council-tax-reduction-2026-2027`,
  which the pin already carries.
- No `key-<32 hex>` editorial anchors and no 32+ character hex runs in the
  source captures.

Contains public sector information licensed under the Open Government Licence
v3.0.
