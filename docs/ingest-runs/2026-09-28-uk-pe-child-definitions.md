# UK child, young person, couple and claimant definitions for PolicyEngine parity

Date: 2026-09-28. Branch `ingest/uk-pe-child-defs`, cut from `origin/main`
c65b2ca15, which contains the `uk-rulespec-2026-09-07` cut (440162d04).

Purpose: policyengine-uk is replacing its generic `is_child` / `is_adult`
flags with each programme's legal definition of a child, qualifying or young
person, couple, lone parent and claimant (branch `remove-is-child-flags`). The
PolicyEngine organisation rule requires the same provisions to be right in
Axiom. rulespec-uk pins `axiom_corpus_release = "uk-rulespec-2026-09-07"`
(`.axiom/toolchain.toml` at rulespec-uk `origin/main` 932390f). None of the
provisions below is in any scope of that release. Several (UC regs 3 and 8, HB
regs 2, 13D, 19 and 75CA, SPC reg 4A, CTC regs 2, 3 and 5, WTC regs 4, 9, 11,
12, 14 and 17, SI 2015/448 reg 9, TCA 2002 s.8) exist only in
`2026-06-01-uk-frs-microsim`, whose rows carry the scope name as their
`expression_date` and so cannot join a `complete-expression-dates-v1`
release. The rest were never ingested. The rulespec-uk tracking issues carry
the `pe-parity` label.

No publication, R2 upload, Supabase load, release selector, activation or
registration step was run. The signed ingest manifests are added in a separate
commit after the clean content commit.

## Commands

Both scopes use version `2026-09-28-uk-pe-child-definitions`, fetched from
legislation.gov.uk CLML (current revised text) on 2026-09-28.

Statute scope (10 provisions):

```bash
uv run --extra dev axiom-corpus-ingest extract-uk-legislation --base data/corpus \
  --version 2026-09-28-uk-pe-child-definitions --source clml \
  --citation ukpga/1992/4/section/137 --citation ukpga/2002/16/section/4 \
  --citation ukpga/2002/16/section/5 --citation ukpga/2002/16/section/17 \
  --citation ukpga/2002/21/section/3 --citation ukpga/2002/21/section/8 \
  --citation ukpga/2007/3/section/55C --citation ukpga/2014/28/section/3 \
  --citation ukpga/2014/28/section/6 --citation ukpga/2016/5/section/1 \
  --source-as-of 2026-09-28 --expression-date 2026-04-06
```

Regulation scope (27 provisions):

```bash
uv run --extra dev axiom-corpus-ingest extract-uk-legislation --base data/corpus \
  --version 2026-09-28-uk-pe-child-definitions --source clml \
  --citation uksi/2013/376/regulation/3 --citation uksi/2013/376/regulation/8 \
  --citation uksi/2006/213/regulation/2 --citation uksi/2006/213/regulation/13D \
  --citation uksi/2006/213/regulation/19 --citation uksi/2006/213/regulation/75CA \
  --citation uksi/2002/1792/regulation/4A \
  --citation uksi/2002/2007/regulation/2 --citation uksi/2002/2007/regulation/3 \
  --citation uksi/2002/2007/regulation/5 \
  --citation uksi/2002/2005/regulation/4 --citation uksi/2002/2005/regulation/9 \
  --citation uksi/2002/2005/regulation/11 --citation uksi/2002/2005/regulation/12 \
  --citation uksi/2002/2005/regulation/14 --citation uksi/2002/2005/regulation/17 \
  --citation uksi/2015/448/regulation/3 --citation uksi/2015/448/regulation/9 \
  --citation uksi/2006/223/regulation/3 \
  --citation uksi/1987/1967/regulation/2 --citation uksi/1987/1967/regulation/14 \
  --citation uksi/1987/1967/schedule/2/paragraph/1 \
  --citation uksi/2022/1134/regulation/14 --citation uksi/2022/1134/regulation/15 \
  --citation uksi/2011/1986/regulation/42 --citation uksi/2011/1986/regulation/45 \
  --citation uksi/2011/1986/regulation/46 \
  --source-as-of 2026-09-28 --expression-date 2026-04-06
```

Both runs reported `coverage_complete: true`, 0 missing, 0 extra (statute
10/10, regulation 27/27).

Provision files (sha256):

- `data/corpus/provisions/uk/statute/2026-09-28-uk-pe-child-definitions.jsonl`
  `03a70693e95d68c17e887fdf6290497ca3b96e2e1288657b29339030ca2cddfe` (10 rows)
- `data/corpus/provisions/uk/regulation/2026-09-28-uk-pe-child-definitions.jsonl`
  `e5b824162aad96da4f5cd2acfe44506cbe6680624de41327d61481f4acd97556` (27 rows)

## Expression date

The extractor fetches the current revised text. The rows carry
`expression_date` 2026-04-06, the start of the 2026-27 benefit and tax year,
as `2026-07-06-uk-tax-credits-rates` and `2026-06-05-uk-child-benefit-sscba`
did. Before using that date I read the `RestrictStartDate` of every element
inside each fetched provision's `Body` or `Schedules`, excluding the
enclosing `Part`, `Chapter` and `Pblock` containers, which carry
instrument-wide dates. No element was marked `Status="Prospective"`. The
latest start date in each provision is on or before 2026-04-06, so the
fetched text is the text in force on that date:

| Provision | Latest element start |
|---|---|
| ukpga/1992/4 s.137 | 2019-12-02 |
| ukpga/2002/16 s.4 / s.5 / s.17 | 2024-06-08 / 2005-12-05 / 2026-03-15 |
| ukpga/2002/21 s.3 / s.8 | 2019-12-02 / 2002-07-09 |
| ukpga/2007/3 s.55C | 2026-03-18 |
| ukpga/2014/28 s.3 / s.6 | 2018-02-14 / 2018-02-14 |
| ukpga/2016/5 s.1 | 2022-03-25 |
| uksi/2013/376 reg 3 / reg 8 | 2013-04-29 / 2022-07-01 |
| uksi/2006/213 reg 2 / 13D / 19 / 75CA | 2026-03-15 / 2017-04-01 / 2013-04-29 / 2023-04-01 |
| uksi/2002/1792 reg 4A | 2016-07-28 |
| uksi/2002/2007 reg 2 / 3 / 5 | 2020-12-01 / 2017-04-06 / 2020-04-06 |
| uksi/2002/2005 reg 4 / 9 / 11 / 12 / 14 / 17 | 2024-04-06 / 2021-12-09 / 2012-04-06 / 2003-04-06 / 2022-06-09 / 2024-03-13 |
| uksi/2015/448 reg 3 / reg 9 | 2015-03-05 / 2026-04-06 |
| uksi/2006/223 reg 3 | 2025-09-01 |
| uksi/1987/1967 reg 2 / reg 14 / Sch 2 para 1 | 2026-03-15 / 2013-04-29 / 2026-04-06 |
| uksi/2022/1134 reg 14 / reg 15 | 2023-03-30 / 2023-03-30 |
| uksi/2011/1986 reg 42 / 45 / 46 | 2020-12-31 / 2026-03-05 / 2025-03-06 |

The instrument-level `Legislation` and `Body` dates (for example 2026-09-16
on ITA 2007 and 2026-07-16 on SI 2013/376) record changes elsewhere in the
instrument, not in these provisions.

## Held out: SPC Regs 2002 Schedule I paragraphs 1, 2 and 4

`--citation uksi/2002/1792/schedule/I/paragraph/1` fails with "section,
regulation, article, schedule, or appendix required".
`UK_SCHEDULE_LIKE_PATTERN` in `src/axiom_corpus/models_uk.py` accepts only a
container number that starts with a digit (`\d+[A-Za-z]*`), so the roman
numeral `I` is parsed as a sub-paragraph path. A local-CLML run
(`--source-xml` of the three paragraph files) collapses all three to the
citation path `uk/regulation/uksi/2002/1792/schedule`. Ingesting them needs
roman-numeral schedule support in the UK citation grammar first. They are not
in this scope.

## Validation

- `extract-uk-legislation`: coverage complete for both classes.
- `scripts/validate_citation_paths.py`: `uppercase_segments` 16282 against a
  baseline of 16281 before the ratchet. The one new irregular path is the
  genuine inserted section `uk/statute/ukpga/2007/3/55C`. The three other
  upper-case paths (`2006/213/13D`, `2006/213/75CA` and `2002/1792/4A`)
  already exist in `2026-06-01-uk-frs-microsim`. The baseline was raised by
  one with `--update-baselines`, which changed only that line of
  `schema/citation-path.v1.json`. The script then passes.
- `validate-release` on scratch one-scope selectors for each class: `ok: true`,
  0 errors, 0 warnings.
- `validate-release` on an uncommitted draft selector (`uk-rulespec-2026-09-07`
  plus both new scopes, profile `complete-expression-dates-v1`, 193 scopes):
  `ok: true`, 0 errors, 0 warnings.
- No `key-<32 hex>` editorial anchors and no 32+ character hex runs in the
  source captures.
