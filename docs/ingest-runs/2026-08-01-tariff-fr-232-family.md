# US tariff FR instruments: section 232 family

Parity lane A (rulespec-us#1190, follow-on to the T0 run documented in
`2026-08-01-tariff-t0-title-19-hts-fr.md`). This run retains every operative
section 232 Federal Register instrument referenced by the tariff encoding
lane's authority checklist, from the original 2018 metals proclamations
through the June 2026 derivative expansion, plus the three implementing
notices that carry heading-level mechanics (inclusions process, the
Canada/Mexico steel and aluminum tariff-adjustment procedures under
Proclamation 10984, Taiwan MOU implementation).

All fifteen scopes are `us/rulemaking` versions extracted with
`extract-federal-register` from the federalregister.gov API (full-text bodies
plus metadata), pinned to the publication date with `--source-as-of
2026-08-01` and `--expression-date` equal to the publication date. Every
query was pre-flighted against the API so that the stored inventory is
exactly the expected document set — no same-day noise documents are
retained. Citation paths are
`us/rulemaking/federal-register/{publication-date}/{document-number}`.

## Scopes in this run

| Version (prefix `2026-08-01-tariff-`) | Pub date | FR doc(s) | Instrument |
| --- | --- | --- | --- |
| `232-originals-2018-types-presdocu-term-adjusting-imports` | 2018-03-15 | 2018-05477, 2018-05478 | Proc. 9704 (aluminum) and Proc. 9705 (steel), the original section 232 metals actions |
| `232-russia-aluminum-types-presdocu-term-aluminum` | 2023-03-02 | 2023-04470 | Proc. 10522, 200 percent duty on Russian aluminum |
| `232-metals-feb-2025-types-presdocu-term-adjusting-imports` | 2025-02-18 | 2025-02832, 2025-02833 | Proc. 10895 (aluminum) and Proc. 10896 (steel), exemption revocations effective 2025-03-12 |
| `232-autos-types-presdocu-term-automobiles` | 2025-04-03 | 2025-05930 | Proc. 10908, automobiles and automobile parts |
| `232-metals-50pct-types-presdocu-term-aluminum-and-steel` | 2025-06-09 | 2025-10524 | Proc. 10947, aluminum and steel rate increase to 50 percent |
| `232-copper-types-presdocu-term-copper` | 2025-08-05 | 2025-14893 | Proc. 10962, copper |
| `232-inclusions-process-types-notice-term-tariff-inclusions-process` | 2025-08-19 | 2025-15819 | Commerce/BIS adoption and procedures of the steel and aluminum tariff inclusions process |
| `232-wood-types-presdocu-term-timber` | 2025-10-06 | 2025-19482 | Proc. 10976, timber, lumber, and derivative products |
| `232-mhd-buses-types-presdocu-term-adjusting-imports-of-trucks` | 2025-10-22 | 2025-19639 | Proc. 10984, medium- and heavy-duty vehicles, parts, and buses |
| `232-semiconductors-types-presdocu-term-semiconductors` | 2026-01-20 | 2026-01052 | Proc. 11002, semiconductors, manufacturing equipment, and derivatives |
| `232-annex-restructure-types-presdocu-term-strengthening-actions` | 2026-04-09 | 2026-06960 | Proc. 11021, strengthening actions restructuring the aluminum/steel/copper annexes |
| `232-pharmaceuticals-types-presdocu-term-pharmaceuticals` | 2026-04-09 | 2026-06956 | Proc. 11020, pharmaceuticals and pharmaceutical ingredients |
| `232-usmca-parts-procedures-types-notice-term-9903-82-18` | 2026-04-23 | 2026-07987 | Commerce procedures notice under Proc. 10984 for Canada/Mexico steel and aluminum producers committing to new U.S. production to obtain tariff adjustments; its annex adds headings 9903.82.18/.19 for limited quantities of USMCA-qualifying steel and aluminum (91 FR 21790, cited by the tracker on 2026 Rev 6) |
| `232-taiwan-mou-types-notice-term-taipei` | 2026-05-28 | 2026-10571 | Implementation notice for the AIT–TECRO trade and security agreement elements (232 auto-parts/wood/aircraft-component carve-outs) |
| `232-metals-expansion-types-presdocu-term-further-adjusting` | 2026-06-04 | 2026-11314 | Proc. 11032, further adjusting the aluminum/steel/copper tariff regimes (derivative expansion effective 2026-06-08) |

The section 232 aluminum modification of 2026-07-23 (2026-14990) was already
retained by the T0 run and is not repeated here.

## Verification

- Every version's coverage report is complete (extractor exits nonzero
  otherwise): source count equals provision count equals matched count.
- Post-extraction, each version's inventory was independently checked to
  contain exactly the expected Federal Register document numbers listed
  above (pre-flight and post-check share the same API conditions).
- Presidential document numbers (proclamation numbers) above come from the
  federalregister.gov API metadata for the same documents, except
  Proclamations 9704 and 9705, whose stored API metadata carries no
  proclamation-number field: those numbers appear in the stored full-text
  bodies of 2018-05477 and 2018-05478 themselves.

## Downstream

These instruments are the authority text for the section 232 Chapter 99
headings as expressed in the HTS revision snapshots, feeding the tariff
encodings in `rulespec-us` and the `us_tariff` oracle suite in
`axiom-oracles`. New citation paths widen the pending `us` release cut.
