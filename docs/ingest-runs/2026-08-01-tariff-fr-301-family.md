# US tariff FR instruments: section 301 family

Parity lane A (rulespec-us#1190, follow-on to the T0 run documented in
`2026-08-01-tariff-t0-title-19-hts-fr.md`). This run retains the section 301
USTR notices beyond the boundary documents already in T0 (the forced-labor
and Brazil 301 action notices): the quadrennial-review modifications, the
exclusion-extension rounds, and the initiation notices for the Brazil and
forced-labor investigations.

All ten scopes are `us/rulemaking` versions extracted with
`extract-federal-register` from the federalregister.gov API (full-text
bodies plus metadata), pinned to the publication date with `--source-as-of
2026-08-01` and `--expression-date` equal to the publication date. Every
query was pre-flighted against the API so that the stored inventory is
exactly the expected document set. Citation paths are
`us/rulemaking/federal-register/{publication-date}/{document-number}`.

## Scopes in this run

| Version (prefix `2026-08-01-tariff-`) | Pub date | FR doc | Instrument |
| --- | --- | --- | --- |
| `301-exclusions-may-2024-types-notice-term-extension-of-certain-exclusions` | 2024-05-30 | 2024-11904 | Extension of certain exclusions (China technology-transfer action) |
| `301-quadrennial-sep-2024-types-notice-term-technology-transfer` | 2024-09-18 | 2024-21217 | Notice of modification: quadrennial-review actions (rate schedule for the 9903.91.xx tiers) |
| `301-quadrennial-dec-2024-types-notice-term-china-s-acts-policies-and-practices` | 2024-12-16 | 2024-29462 | Notice of modification: further quadrennial-review actions |
| `301-exclusions-jun-2025-types-notice-term-product-exclusion-extensions` | 2025-06-05 | 2025-10203 | Product exclusion extensions |
| `301-exclusions-sep-2025-types-notice-term-product-exclusion-extensions` | 2025-09-02 | 2025-16733 | Product exclusion extensions |
| `301-exclusions-dec-2025-types-notice-term-exclusion-extensions` | 2025-12-01 | 2025-21671 | Product exclusion extensions |
| `301-brazil-initiation-types-notice-term-brazil` | 2025-07-18 | 2025-13498 | Initiation of the Brazil digital-trade section 301 investigation |
| `301-brazil-determination-types-notice-term-digital-trade` | 2026-06-04 | 2026-11158 | Notice of determination and request for comments (Brazil) |
| `301-fl-initiation-types-notice-term-forced-labor` | 2026-03-17 | 2026-05151 | Initiation of the forced-labor section 301 investigations of various economies |
| `301-fl-determinations-types-notice-term-forced-labor` | 2026-06-05 | 2026-11296 | Notice of determinations and request for comments (forced labor) |

The forced-labor and Brazil action notices themselves (2026-15181,
2026-15274, 2026-14542, 2026-14654) were already retained by the T0 run and
are not repeated here.

## Verification

- Every version's coverage report is complete (extractor exits nonzero
  otherwise): source count equals provision count equals matched count.
- Post-extraction, each version's inventory was independently checked to
  contain exactly the expected Federal Register document numbers listed
  above (pre-flight and post-check share the same API conditions). The
  December 2024 quadrennial query uses the phrase "china's acts, policies,
  and practices" because a same-day NSF notice also matches "technology
  transfer".

## Downstream

These notices carry the rate schedules and exclusion windows behind the
section 301 Chapter 99 headings (the 9903.88.xx and 9903.91.xx families and
the forced-labor 9903.05/9903.06 tiers) expressed in the HTS revision
snapshots, feeding the tariff encodings in `rulespec-us` and the `us_tariff`
oracle suite in `axiom-oracles`. New citation paths widen the pending `us`
release cut.
