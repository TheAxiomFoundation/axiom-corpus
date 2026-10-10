# US tariff FR instruments: IEEPA and trade-framework family

Parity lane A (rulespec-us#1190, follow-on to the T0 run documented in
`2026-08-01-tariff-t0-title-19-hts-fr.md`). This run retains the IEEPA
tariff executive orders (fentanyl/border, reciprocal, Brazil, Russia
secondary, de minimis) and the trade-framework implementation instruments
(Japan, framework scope/procedures, UK, Switzerland-Liechtenstein).

All nineteen scopes are `us/rulemaking` versions extracted with
`extract-federal-register` from the federalregister.gov API (full-text
bodies plus metadata), pinned to the publication date(s) with
`--source-as-of 2026-08-01` and `--expression-date` equal to the (first)
publication date. Every query was pre-flighted against the API so that the
stored inventory is exactly the expected document set. Citation paths are
`us/rulemaking/federal-register/{publication-date}/{document-number}`.

## Scopes in this run

### IEEPA fentanyl/border chain (5 versions, 11 documents)

| Version (prefix `2026-08-01-tariff-`) | Pub date(s) | FR doc(s) | Instrument |
| --- | --- | --- | --- |
| `ieepa-fentanyl-eos-types-presdocu-term-imposing-duties-to-address` | 2025-02-07 | 2025-02406, 2025-02407, 2025-02408 | EO 14193 (Canada), EO 14194 (Mexico), EO 14195 (China) — the original IEEPA duty orders |
| `ieepa-fentanyl-pauses-types-presdocu-term-progress-on-the-situation` | 2025-02-10 | 2025-02478, 2025-02479 | EO 14197 (Canada pause), EO 14198 (Mexico pause) |
| `ieepa-fentanyl-china-amend-types-presdocu-term-synthetic-opioid` | 2025-02-11 | 2025-02512 | EO 14200, China de minimis amendment |
| `ieepa-fentanyl-mar-amends-types-presdocu-term-amendment-to-duties` | 2025-03-06 – 2025-03-07 | 2025-03728, 2025-03729, 2025-03775 | EO 14226 (Canada), EO 14227 (Mexico), EO 14228 (China further amendment) |
| `ieepa-fentanyl-usmca-amends-types-presdocu-term-amendment-to-duties` | 2025-03-11 | 2025-03990, 2025-03991 | EO 14231 (Canada USMCA carve-out), EO 14232 (Mexico USMCA carve-out) |

### IEEPA reciprocal chain (6 versions, 7 documents)

| Version | Pub date(s) | FR doc(s) | Instrument |
| --- | --- | --- | --- |
| `ieepa-reciprocal-eo-types-presdocu-term-reciprocal-tariff` | 2025-04-07 | 2025-06063 | EO 14257, the reciprocal tariff order |
| `ieepa-recip-amend-apr-types-presdocu-term-reciprocal` | 2025-04-14 – 2025-04-15 | 2025-06378, 2025-06462 | EO 14259 (low-value imports amendment), EO 14266 (retaliation/alignment modification and 90-day pause) |
| `ieepa-recip-geneva-types-presdocu-term-reciprocal` | 2025-05-21 | 2025-09297 | EO 14298, China Geneva modification |
| `ieepa-recip-extension-types-presdocu-term-reciprocal` | 2025-07-10 | 2025-12962 | EO 14316, extending the modification |
| `ieepa-recip-further-mod-types-presdocu-term-reciprocal` | 2025-08-06 | 2025-15010 | EO 14326, further modifying the reciprocal tariff rates (country-tier annexes) |
| `ieepa-recip-china-ext-types-presdocu-term-reciprocal` | 2025-08-14 | 2025-15554 | EO 14334, China extension |

### IEEPA Brazil, Russia, de minimis (4 versions, 4 documents)

| Version | Pub date | FR doc | Instrument |
| --- | --- | --- | --- |
| `ieepa-brazil-eo-types-presdocu-term-brazil` | 2025-08-05 | 2025-14896 | EO 14323, addressing threats by the Government of Brazil |
| `ieepa-brazil-scope-mod-types-presdocu-term-brazil` | 2025-11-26 | 2025-21417 | EO 14361, modifying the scope of the Brazil tariffs |
| `ieepa-russia-secondary-types-presdocu-term-russian-federation` | 2025-08-11 | 2025-15267 | EO 14329, secondary tariffs addressing the Russian Federation (India) |
| `ieepa-de-minimis-eo-types-presdocu-term-de-minimis` | 2025-08-05 | 2025-14897 | EO 14324, suspending duty-free de minimis treatment for all countries |

### Trade-framework implementation (4 versions, 4 documents)

| Version | Pub date | FR doc | Instrument |
| --- | --- | --- | --- |
| `framework-japan-types-presdocu-term-japan` | 2025-09-09 | 2025-17389 | EO 14345, implementing the United States–Japan agreement |
| `framework-trade-security-types-presdocu-term-trade-and-security` | 2025-09-10 | 2025-17507 | EO 14346, modifying reciprocal-tariff scope and establishing framework implementation procedures |
| `framework-uk-epd-types-presdocu-term-united-kingdom` | 2025-06-23 | 2025-11473 | EO 14309, implementing the US–UK Economic Prosperity Deal |
| `framework-swiss-types-notice-term-switzerland` | 2025-12-18 | 2025-23316 | Notice implementing tariff-related elements of the US–Switzerland–Liechtenstein framework (effective 2025-11-14) |

## Verification

- Every version's coverage report is complete (extractor exits nonzero
  otherwise): source count equals provision count equals matched count.
- Post-extraction, each version's inventory was independently checked to
  contain exactly the expected Federal Register document numbers listed
  above (pre-flight and post-check share the same API conditions).
- Executive order numbers above come from the federalregister.gov API
  metadata for the same documents.

## Downstream

These instruments are the authority text for the IEEPA-era Chapter 99
headings expressed in the 2025 HTS revision snapshots (terminated 2026-02-24
by the instruments already retained in T0) and for the framework/floor rate
structures, feeding the tariff encodings in `rulespec-us` and the
`us_tariff` oracle suite in `axiom-oracles`. New citation paths widen the
pending `us` release cut.
