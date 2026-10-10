# USITC HTS 2026 Revision 15 + UK pharmaceutical FR notice

This source-first run extends the US tariff parity corpus window (lane F,
rulespec-us#1190 / axiom-oracles#444) from 2026 Revision 14 to the current
HTS release, Revision 15, and ingests the Federal Register instrument that
drives Revision 15's single substantive change.

## Scope

| Version | Content | Provisions | SHA-256 (source) |
| --- | --- | ---: | --- |
| `2026-08-04-usitc-hts-2026-rev15` | Full-schedule JSON snapshot, chapters 72/76/95/9903 normalized | 1,707 | `59a76c12e28d7a28975f31a8876bfb08e64927b922fe2b4f88801ff4459181e6` |
| `2026-08-04-usitc-hts-2026-rev15-notes` | General Note 3 + Chapter 99 notes PDFs, release `2026HTSRev15` | 815 | GN3 `a2cf79ac…`, Ch99 `92822e8f…` |
| `2026-08-04-tariff-232-pharma-uk-types-notice-term-patented-pharmaceuticals` | FR 2026-15799 (91 FR 49406, BIS notice) | 3 | per inventory |

## Revision 15 characterization

- Published **August 3, 2026** (change record header); expression date
  2026-08-03.
- The USITC change record lists exactly one item: **9903.04.63 Modified
  (rates of duty), effective July 31, 2026, source: Notice** — the UK
  patented-pharmaceutical section 232 rate reduced from `+ 10%` to `+0%`.
- Independent full-surface diff of the retained Revision 15 bytes against
  the retained Revision 14 snapshot on the normalized surface (all 1,706
  chapter 72/76/95/9903 rows): identical citation-path sets; exactly two
  body differences — the 9903.04.63 rate change above and a one-character
  whitespace correction in the 9903.03.06 description
  ("vehicles;wood" → "vehicles; wood"). Chapters 72, 76, and 95 are
  byte-stable.
- The driving instrument is **FR 2026-15799** (Bureau of Industry and
  Security, docket 260731-0181): tariff on patented pharmaceuticals and
  associated pharmaceutical ingredients of the United Kingdom reduced to
  zero per Proclamation 11020 (91 FR 18183) and the U.S.–UK pharmaceutical
  pricing arrangement, effective 12:01 a.m. ET July 31, 2026. Published
  2026-08-04 — after the lane A instrument sweep (2026-08-01), which is why
  it was not previously in corpus.

## Source and provenance notes

- At ingest time USITC had **not yet published the static full-edition
  JSON** for Revision 15 (`hts_2026_revision_15_json.json` returns the
  usitc.gov 404 page). The retained source bytes are the official
  `hts.usitc.gov/reststop/exportList?from=0101&to=9999&format=JSON&styles=false`
  response, fetched while `reststop/currentRelease` reported `2026HTSRev15`
  immediately before and immediately after the download. Internet Archive
  Save Page Now returned no capture during the ingest window (three
  attempts; timeouts), so Wayback fields are null — the Revision 11
  precedent from the 2026 gapfill run. Row count (35,789) and the
  chapter breakdown (740/182/162/622) exactly match the Revision 14
  static-file structure.
- Notes PDFs are release-pinned via the `reststop/file?release=2026HTSRev15`
  endpoint, digests distinct from the Revision 14 pair.
- The FR ingest used the standard `extract-federal-register` pipeline; the
  query (`2026-08-04`, NOTICE, term "patented pharmaceuticals") matches
  exactly one document, FR 2026-15799.

## Verification

- Snapshot reproducer verifies input SHA-256/byte size, total and per-chapter
  row counts, HTS-number and citation-path uniqueness, source-byte equality,
  full metadata equality on every normalized row, and regime anchors:
  - `9903.04.63`: "Patented pharmaceutical articles that are the product of
    the United Kingdom" + "The duty provided in the applicable subheading +0%"
    (the Revision 15 change);
  - `9903.05.20`: "articles the product of Algeria" + "+ 12.5%" (forced-labor
    section 301 finalization continuity);
  - `9903.03.01`: "+ 10%" (section 122 heading text continuity);
  - `7202.11.10.00`: "Rates of duty (1-General): 1.4%" (stable MFN anchor).
- All three extractions/coverage reports complete (1,707 / 815 / 3 provisions;
  `extra_count` 0, `missing_count` 0, `errors` []).
- Focused corpus suite: 4,179 passed, 79 skipped.
- Signed ingest manifests (Ed25519, key-id `axiom-corpus-ingest-v1`) for all
  three versions; `guard-ingested` passes against origin/main.

## Reproduce

```bash
uv run --extra dev python scripts/repro/us_hts_tariff_snapshots_2026_rev15.py \
  --base data/corpus

uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-08-04-usitc-hts-2026-rev15-notes \
  --manifest manifests/us-usitc-hts-2026-rev15-notes.yaml

uv run --extra dev axiom-corpus-ingest extract-federal-register \
  --base data/corpus \
  --version 2026-08-04-tariff-232-pharma-uk \
  --start-date 2026-08-04 \
  --document-type NOTICE \
  --term "patented pharmaceuticals" \
  --source-as-of 2026-08-04 \
  --expression-date 2026-08-04
```

## Downstream

These versions provide the Revision 15 comparison surface for the US tariff
parity lanes. Downstream note for the parity harness: 9903.04.63 is not
encoded in rulespec-us (grep-verified) and is not on the panel witness
surface, so no encoding or panel movement follows from this ingest. This
ingest does not publish to R2, load Supabase, activate a release, or modify
downstream repositories. The added versions widen the pending `us` release
cut on the existing `us/statute/hts` and `us/rulemaking/federal-register`
citation roots.
