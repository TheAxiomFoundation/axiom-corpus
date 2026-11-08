# Belgian statute promotion for joint personal income tax

Date: 2026-11-03. Branch `ingest/be-rulespec-2026-11-03-pit-pages`, cut from `origin/main`
4a7f91770. `scripts/repro/be_rulespec_2026_11_03_promotion.py` builds the scope
`be/statute/2026-11-03-be-rulespec-source-promotion` and the selector
`manifests/releases/be-rulespec-2026-11-03.json`, and
`tests/test_be_rulespec_2026_11_03_promotion.py` checks them.

rulespec-be pins `be-rulespec-2026-07-10` (rulespec-be `.axiom/toolchain.toml` on `main`
530849e4d5). `be-rulespec-2026-08-29` (axiom-corpus#626, published 2026-08-30) moved
`be/statute` to `2026-08-23-be-rulespec-source-promotion`. That scope holds 67 pages of the
Code des impots sur les revenus 1992 (CIR 92) for income 2025, at
`be/statute/fisconetplus/cir92/revenus-2025/page-<n>`, and rulespec-be never re-pinned to it.

An encoding plan for rulespec-be's joint personal income tax pipeline asked for 16 more pages:
75, 77, 80, 91 to 94, 98, 157 to 159, 175, 176, 191, 273 and 274. No `be/statute` scope in any
release selector carries them. The full export, `be/statute/2026-06-30-be-income-tax-consolidated`,
holds 743 pages.

No publication, Supabase load, activation or registration step ran here. I signed and locked the
scope in the commit after the one that added this note.

## Page set

A page can carry the end of one article and the start of the next, so a requested page can
hold part of an article. The reproducer adds every page of each article with text on a requested
page, and repeats that for the pages it adds until no such article reaches a page outside the
scope (`article_closure`).

Each article runs from the page with its heading, `Article <n>, CIR 92 (revenus 2025)`, to the
page that holds the next heading. When nothing but a section label such as `C. - Profits` sits
above that next heading, the article ends on the page before. The export's table of contents on
pages 3 to 32 repeats the headings, and none of its entries reaches past page 32.

That adds 36 pages: the 16 requested and 20 more (74, 76, 78, 79, 81, 82, 97, 99 to 109, 155
and 156). With them, the release holds the whole text of every article on an added page:

| Articles | Pages | Added here | Already in the 08-23 scope |
| --- | --- | --- | --- |
| 24 to 32 (12 articles, with 25/1, 27/1 and 31bis) | 73 to 82 | 74 to 82 | 73 |
| 33 to 39 (10 articles, with 33bis, 37bis and 38/1) | 91 to 109 | 91 to 94, 97 to 109 | 95, 96 |
| 75 to 80 | 155 to 160 | 155 to 159 | 160 |
| 103 to 106, and 107 to 111 under one heading | 175, 176 | 175, 176 | none |
| 143 to 145 | 190 to 192 | 191 | 190, 192 |
| 171 | 268 to 275 | 273, 274 | 268 to 272, 275 |

Articles 32/1 and 32/2 sit on pages 83 to 90 and have no text on an added page, so the scope
leaves them out.

## Commands

```bash
uv run --extra dev python scripts/repro/be_rulespec_2026_11_03_promotion.py promote --base data/corpus
uv run --extra dev python scripts/repro/be_rulespec_2026_11_03_promotion.py release
```

`promote` reads the 08-23 scope and the full export from `data/corpus` and makes no network
call.

## What the scope holds

- 220 provisions: the 184 rows of the 08-23 scope with new `version` and `source_path` values,
  and, for each added page, the full export's row with new `version`, `expression_date`
  (2026-06-30) and `source_path` values. Each added row keeps the full export's `id` and hangs
  from the scope's own `be/statute/fisconetplus/cir92/revenus-2025` row.
- 11 inputs. Ten match the 08-23 inputs byte for byte. The CIR input
  (`axiom-corpus-9be12db7c693-2026-06-30-be-income-tax-consolidated.selected.jsonl`) holds the
  full export's raw line for each of its 52 earlier citations and 36 added pages: 88 lines, in
  the export's order.
- An inventory item per row, naming its input and that input's sha256, and complete coverage:
  220 of 220.

Against rulespec-be's pin, the release changes only `be/statute`: the 169 rows of
`2026-07-10-be-rulespec-source-promotion` all appear in the new scope, where only `version` and
`source_path` differ, and the new scope holds 51 more pages.

## Checks

- The reproducer rebuilds all 14 scope files and the selector byte for byte.
- `validate-release --strict-warnings` on `be-rulespec-2026-11-03`: `ok`, 13 scopes, 0 errors,
  0 warnings.
- The test writes out the requested pages, the added pages and the 37 article headings above, so a
  wrong page in the reproducer fails it. It also checks the rows, the CIR input lines and the
  ten unchanged inputs against the 08-23 scope and the full export.
- Hypothesis properties cover `promote_rows`, `select_input_lines` and `article_closure` on
  synthetic scopes, including the refusals. Nine mutants of the reproducer each fail at least
  one test.
- Every row's `id` matches the path-only identity that `scripts/validate_citation_paths.py`
  accepts, and every added citation path already sits in the full export, so neither of that
  script's ratchets moves. CI runs its full scan.

## After merge

1. Dispatch `publish.yml`, then `mirror-release.yml`. **Publish only. Do not activate it.** It
   serves as a pin release for rulespec-be; see `docs/named-release-publication.md`.
2. Re-pin rulespec-be to this release: `.axiom/toolchain.toml` (`axiom_corpus_release` and
   `axiom_corpus_release_content_sha256`), and the corpus commit in
   `.github/workflows/repository-checks.yml` (`axiom-corpus-ref`) and, where the file exists,
   `.axiom/workflow-toolchain.toml` (`axiom_corpus_ref`).
