# Erratum: California LegInfo concurrent versions

Recorded 2026-10-22 for
[`2026-09-26-us-ca-leginfo-concurrent-versions.md`](2026-09-26-us-ca-leginfo-concurrent-versions.md).

The original note is unchanged because the ingest manifest records its SHA-256
in `reasoning_logs`, and the Ed25519 signature covers that entry. Its recorded
and current hash is
`dba38908eac77476e7f398481381a954f3497a0ef9037830d743fd7872af38da`.
This erratum corrects the comparison claim without changing the signed evidence
or corpus artifacts.

## Source-version identity and legacy extraction differences

The original note says that the plain rows differ from their variants only in
the history note. That overstates what the test establishes. The comparison
identifies the same LegInfo version by `source_id`/`sectionuid` and the op triple,
then re-extracts each legacy row's retained source HTML with the current table
extractor and compares that result with the variant body, excluding the final
history line. It does not compare the legacy row's stored normalized `body`
with the variant's stored normalized `body`.

The executed review of PR #752 at `33b38a424` measured the original CalWORKs
WIC 11450 normalized body at **29,167 UTF-8 bytes**, with **one `(ib)`** marker.
The `--operative-2021-07-01` variant has **30,102 UTF-8 bytes**, with **two `(ib)`**
markers. These bodies remain unequal after the history note is removed. They
therefore have known differences from their extraction history in addition to
the updated LegInfo history note; this PR does not repair the legacy body or
claim byte equality with it. The source-version mapping in the original table
is the mapping checked by the test.

The legacy extractor collects paragraph and italic blocks and drops repeated
block text. The table-preserving extractor emits table rows and cells and keeps
repeated paragraphs. The CalWORKs table-preserving successor already has the
30,102-byte body with two `(ib)` markers. A fresh comparison of the locked
artifacts on 2026-10-22 confirmed these counts and the shared `sectionuid`
`id_8bd4339c-b1a3-11ef-8ee0-67d76dc08b34` across all three rows.

For WIC 11450, the retained sources' final history lines also differ: the older
capture names `Sec. 2 of Stats. 2024, Ch. 798.`, and the concurrent-version scope
names `Sec. 2 of Stats. 2026, Ch. 310.`. Re-extracting the retained HTML with the
same extractor and accounting for that history change supports source-version
identity, while preserving the distinction from normalized-body equality.
