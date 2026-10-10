# USITC HTS 2026 gapfill snapshots

This source-first run fills the 11 remaining 2026-edition Harmonized Tariff
Schedule (HTS) snapshots needed by the US tariff parity campaign: the Basic
Edition and Revisions 1, 2, 5–11, and 13. Revisions 3, 4, 12, and 14 remain in
the separate T0 scope and are not re-ingested here.

Every version uses citation root `us/statute/hts`. The version distinguishes
the snapshot while provision paths remain stable at
`us/statute/hts/{htsno}`.

## Scope

The expression date is the USITC `releaseStartDate`. The Yale cover date is
recorded independently and is null for Revision 8, which Yale excludes from
its configured revision chronology, and Revision 13, which postdates the Yale
mirror set used for verification.

| Snapshot | Version | Expression date | Yale cover date | Wayback capture | Body gzip | Bytes | Total rows | Target rows | 72 / 76 / 95 / 9903 | SHA-256 |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| Basic | `2026-08-01-usitc-hts-2026-basic` | 2025-12-31 | 2026-01-01 | 20260624200855 | true | 13,642,171 | 35,571 | 1,772 | 738 / 181 / 162 / 691 | `a718007c8455c93a88ddc68f15f036cee10e9a820065a4c356da1481f4131858` |
| Revision 1 | `2026-08-01-usitc-hts-2026-rev1` | 2026-01-16 | 2026-01-16 | 20260624200855 | true | 13,648,615 | 35,580 | 1,781 | 738 / 181 / 162 / 700 | `8d258c60f75c09f2f61c8e184aa8f38b5a3f7ba0e0edcfc608282ca51cbc8ef2` |
| Revision 2 | `2026-08-01-usitc-hts-2026-rev2` | 2026-01-30 | 2026-01-30 | 20260624200856 | true | 13,690,141 | 35,720 | 1,781 | 738 / 181 / 162 / 700 | `b56567588ca6165772d409d7ad097e7b96327fa7f19d18b6a95f70317ad864a1` |
| Revision 5 | `2026-08-01-usitc-hts-2026-rev5` | 2026-04-08 | 2026-04-06 | 20260624200856 | true | 13,471,071 | 35,493 | 1,568 | 738 / 182 / 162 / 486 | `0e6117efc73e98a8b0203205e8e7f09e6a6a9aa2c793f15def3680d447d68448` |
| Revision 6 | `2026-08-01-usitc-hts-2026-rev6` | 2026-04-23 | 2026-04-23 | 20260624200856 | true | 13,472,235 | 35,495 | 1,570 | 738 / 182 / 162 / 488 | `8258abee12b65e04a1c5b04519377040c711b8c31653d2b069fbf5e87a00e4d8` |
| Revision 7 | `2026-08-01-usitc-hts-2026-rev7` | 2026-04-29 | 2026-04-29 | 20260624200856 | true | 13,472,793 | 35,496 | 1,571 | 738 / 182 / 162 / 489 | `0a8789f5a540f69117b74855c348ce2aaa62b6e57efe80ef46b45248053e9c37` |
| Revision 8 | `2026-08-01-usitc-hts-2026-rev8` | 2026-05-22 | null | 20260624200856 | true | 13,472,793 | 35,496 | 1,571 | 738 / 182 / 162 / 489 | `04f4ddda584823a954097b65cd8ca3a5aa1982317c344c582aa4cc3d5021433a` |
| Revision 9 | `2026-08-01-usitc-hts-2026-rev9` | 2026-05-28 | 2026-05-28 | 20260624200856 | true | 13,476,771 | 35,502 | 1,577 | 738 / 182 / 162 / 495 | `2dc811962b6809736e2e30c8753d0d0bc3fb3f1c65bbb15728663959247957ae` |
| Revision 10 | `2026-08-01-usitc-hts-2026-rev10` | 2026-06-08 | 2026-06-08 | 20260624200856 | true | 13,481,362 | 35,509 | 1,584 | 738 / 182 / 162 / 502 | `66375d1cc8e56cae00bbf8327c400e62586eefe128cad7c8e4d936dc3d4eda2f` |
| Revision 11 | `2026-08-01-usitc-hts-2026-rev11` | 2026-07-01 | 2026-07-01 | none | false | 13,572,076 | 35,668 | 1,586 | 740 / 182 / 162 / 502 | `16cc1f30b40430019a52463416baa3cd682f15228b955be5bc44e7dd39e51e30` |
| Revision 13 | `2026-08-01-usitc-hts-2026-rev13` | 2026-07-28 | null | 20260801211320 | true | 12,623,527 | 35,779 | 1,696 | 740 / 182 / 162 / 612 | `3b4057c56e3bfaa48285b5371f771007840ea007c5094772f04c4754b6e3c6a5` |

The 11 retained sources total 148,023,555 bytes and 391,309 source rows.
Normalization emits 18,057 target HTS rows and 18,068 provisions after the
11 document roots are included.

## Source and mirror verification

The Basic Edition and Revisions 1, 2, 6, 7, 8, and 10 are byte-identical to
the correspondingly named Yale Budget Lab mirrors under
`yale-budget-lab/tariff-rate-tracker/data/hts_archives/` after gunzip. Their
gunzip hashes equal the retained source hashes.

- Revision 5 is capture-authoritative. The Wayback capture is the pristine
  Revision 5 static file; the Yale mirror reflects later in-place edits with
  three row-level differences and three mirror-only heading rows.
- Revision 9 is content-identical to the Yale mirror after dropping the
  static file's extra leading `0101` heading row and stripping HTML
  presentation tags.
- Revision 11 has no Wayback timestamp or URL. The retained bytes are the
  gunzip of Yale mirror
  `data/hts_archives/hts_2026_rev_11.json.gz`, SHA-256
  `16cc1f30b40430019a52463416baa3cd682f15228b955be5bc44e7dd39e51e30`.
  The bytes were identical across two independent checkouts. Wayback CDX
  returned 503 during reconnaissance, and three Save Page Now attempts
  returned 520 on 2026-08-01. Its `source_url` remains the official USITC
  static URL; its download provenance is explicitly the Yale mirror gunzip,
  with null Wayback fields.
- Revision 13 is a single-source Wayback capture of the official USITC static
  URL. No Yale mirror exists.

The metadata for every normalized row records the Yale cover date, exact
Wayback fields, Yale mirror path and gunzip hash where applicable, and the
snapshot-specific mirror-verification outcome.

## Verification

The reproducer verifies each input's SHA-256 and byte size before parsing. It
then builds all four artifact classes in a temporary staging directory and
checks:

- the full JSON row count and the exact chapter 72/76/95/9903 breakdown;
- uniqueness of all emitted HTS numbers and citation paths;
- source-byte equality between the input and staged canonical source;
- the version, expression date, official source URL, download URL, and source
  provenance metadata on every normalized row;
- inventory/provision path equality and complete coverage with one document
  root plus every target row; and
- source-derived regime anchors: the stable `1.4%` general rate on
  `7202.11.10.00`, the `+ 10%` lines on `9903.01.25` and `9903.03.01`, the
  absence of `9903.03.01` before Revision 4, the absence of
  `9903.05.20`/`9903.06.01` through Revision 11, and the `+ 12.5%` Algeria
  line on `9903.05.20` in Revision 13.

All 11 coverage reports are complete. The citation root and all descendants
use the existing regular `us/statute/hts/...` path family.

## Reproduce

```bash
uv run --extra dev python scripts/repro/us_hts_tariff_snapshots_2026_gapfill.py \
  --base data/corpus \
  --source-dir /Users/maxghenis/.axiom/workspace/laneA-hts-downloads
```

The source directory may instead be omitted after the canonical source files
have been retained under `data/corpus/sources/`.

## Downstream

These versioned HTS expressions provide the remaining 2026 comparison surface
for the US tariff parity RuleSpec and oracle lanes. This ingest does not
publish to R2, load Supabase, activate a release, or modify downstream
repositories.
