# USITC HTS notes: General Note 3 and Chapter 99 per-revision gapfill

Parity lane A (rulespec-us#1190, follow-on to the T0 run that ingested
`2026-08-01-usitc-hts-2026-rev14-notes`). This run ingests the per-revision
"notes" documents — the General Note 3 and Chapter 99 PDFs — for the 44
remaining HTS releases in the tariff parity window: the 2025 Basic Edition
plus Revisions 1–32, and the 2026 Basic Edition plus Revisions 1, 2, 5–11,
and 13. (2026 Revision 14 was ingested by T0; 2026 Revisions 3, 4, and 12
are outside the assigned gapfill set.)

All 44 scopes are `us/statute` versions extracted with
`extract-official-documents` from the USITC `reststop/file` endpoint,
which honors its `release` parameter and serves release-specific PDFs
(all 88 stored PDFs have distinct SHA-256 digests; per-release digests are
recorded in each version's inventory). Each version stores exactly two
documents under the citation paths `us/statute/hts/general-note-3` and
`us/statute/hts/chapter-99`, with `expression_date` equal to the
release's USITC start date and `--source-as-of 2026-08-01`. All releases
carry `release_status: archive` (only 2026 Revision 14, not in this run,
was current on the fetch date).

## Scopes in this run

| Version | Release | Effective date |
| --- | --- | --- |
| `2026-08-01-usitc-hts-2025-basic-notes` | 2025HTSBasic | 2024-12-31 |
| `2026-08-01-usitc-hts-2025-rev1-notes` | 2025HTSRev1 | 2025-02-05 |
| `2026-08-01-usitc-hts-2025-rev2-notes` | 2025HTSRev2 | 2025-02-12 |
| `2026-08-01-usitc-hts-2025-rev3-notes` | 2025HTSRev3 | 2025-03-06 |
| `2026-08-01-usitc-hts-2025-rev4-notes` | 2025HTSRev4 | 2025-03-11 |
| `2026-08-01-usitc-hts-2025-rev5-notes` | 2025HTSRev5 | 2025-03-14 |
| `2026-08-01-usitc-hts-2025-rev6-notes` | 2025HTSRev6 | 2025-04-03 |
| `2026-08-01-usitc-hts-2025-rev7-notes` | 2025HTSRev7 | 2025-04-04 |
| `2026-08-01-usitc-hts-2025-rev8-notes` | 2025HTSRev8 | 2025-04-09 |
| `2026-08-01-usitc-hts-2025-rev9-notes` | 2025HTSRev9 | 2025-04-11 |
| `2026-08-01-usitc-hts-2025-rev10-notes` | 2025HTSRev10 | 2025-04-15 |
| `2026-08-01-usitc-hts-2025-rev11-notes` | 2025HTSRev11 | 2025-05-02 |
| `2026-08-01-usitc-hts-2025-rev12-notes` | 2025HTSRev12 | 2025-05-13 |
| `2026-08-01-usitc-hts-2025-rev13-notes` | 2025HTSRev13 | 2025-05-16 |
| `2026-08-01-usitc-hts-2025-rev14-notes` | 2025HTSRev14 | 2025-06-06 |
| `2026-08-01-usitc-hts-2025-rev15-notes` | 2025HTSRev15 | 2025-06-20 |
| `2026-08-01-usitc-hts-2025-rev16-notes` | 2025HTSRev16 | 2025-07-01 |
| `2026-08-01-usitc-hts-2025-rev17-notes` | 2025HTSRev17 | 2025-08-01 |
| `2026-08-01-usitc-hts-2025-rev18-notes` | 2025HTSRev18 | 2025-08-07 |
| `2026-08-01-usitc-hts-2025-rev19-notes` | 2025HTSRev19 | 2025-08-18 |
| `2026-08-01-usitc-hts-2025-rev20-notes` | 2025HTSRev20 | 2025-08-27 |
| `2026-08-01-usitc-hts-2025-rev21-notes` | 2025HTSRev21 | 2025-08-29 |
| `2026-08-01-usitc-hts-2025-rev22-notes` | 2025HTSRev22 | 2025-09-09 |
| `2026-08-01-usitc-hts-2025-rev23-notes` | 2025HTSRev23 | 2025-09-16 |
| `2026-08-01-usitc-hts-2025-rev24-notes` | 2025HTSRev24 | 2025-09-26 |
| `2026-08-01-usitc-hts-2025-rev25-notes` | 2025HTSRev25 | 2025-10-10 |
| `2026-08-01-usitc-hts-2025-rev26-notes` | 2025HTSRev26 | 2025-10-31 |
| `2026-08-01-usitc-hts-2025-rev27-notes` | 2025HTSRev27 | 2025-11-07 |
| `2026-08-01-usitc-hts-2025-rev28-notes` | 2025HTSRev28 | 2025-11-10 |
| `2026-08-01-usitc-hts-2025-rev29-notes` | 2025HTSRev29 | 2025-11-17 |
| `2026-08-01-usitc-hts-2025-rev30-notes` | 2025HTSRev30 | 2025-11-21 |
| `2026-08-01-usitc-hts-2025-rev31-notes` | 2025HTSRev31 | 2025-11-28 |
| `2026-08-01-usitc-hts-2025-rev32-notes` | 2025HTSRev32 | 2025-12-05 |
| `2026-08-01-usitc-hts-2026-basic-notes` | 2026HTSBasic | 2025-12-31 |
| `2026-08-01-usitc-hts-2026-rev1-notes` | 2026HTSRev1 | 2026-01-16 |
| `2026-08-01-usitc-hts-2026-rev2-notes` | 2026HTSRev2 | 2026-01-30 |
| `2026-08-01-usitc-hts-2026-rev5-notes` | 2026HTSRev5 | 2026-04-08 |
| `2026-08-01-usitc-hts-2026-rev6-notes` | 2026HTSRev6 | 2026-04-23 |
| `2026-08-01-usitc-hts-2026-rev7-notes` | 2026HTSRev7 | 2026-04-29 |
| `2026-08-01-usitc-hts-2026-rev8-notes` | 2026HTSRev8 | 2026-05-22 |
| `2026-08-01-usitc-hts-2026-rev9-notes` | 2026HTSRev9 | 2026-05-28 |
| `2026-08-01-usitc-hts-2026-rev10-notes` | 2026HTSRev10 | 2026-06-08 |
| `2026-08-01-usitc-hts-2026-rev11-notes` | 2026HTSRev11 | 2026-07-01 |
| `2026-08-01-usitc-hts-2026-rev13-notes` | 2026HTSRev13 | 2026-07-28 |

## Verification

- Every version's coverage report is complete (the extractor exits nonzero
  otherwise); all 44 extractions exited 0 on the first attempt.
- Each inventory contains exactly the two document citation paths above;
  each document has non-empty extracted provisions (General Note 3: 8
  non-empty provisions per release; Chapter 99: 654–800 depending on
  release).
- Regime anchors computed on the extracted Chapter 99 text:
  - `9903.03.01` is absent from every 2025 release and from 2026 Basic,
    Revision 1, and Revision 2; it is present in 2026 Revisions 5–11
    and 13.
  - `9903.01.25` is absent from 2025 Basic through Revision 6 and present
    from 2025 Revision 7 (effective 2025-04-04) onward, including all 2026
    releases in this run. The pre-run expectation ("present in 2025
    Revision 10 and later") was set before extraction; the observed
    first-presence at Revision 7 is what the stored text shows.

## Downstream

These per-revision notes give the tariff encoding lane dated authority text
for the Chapter 99 headings and General Note 3 duty-rate mechanics at each
HTS revision in the parity window, alongside the revision snapshot data,
feeding the tariff encodings in `rulespec-us` and the `us_tariff` oracle
suite in `axiom-oracles`. New citation paths reuse the existing
`us/statute/hts/{general-note-3,chapter-99}` roots; the added versions
widen the pending `us` release cut.
