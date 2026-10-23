# 20 CFR part 416 with its Appendix to Subpart K (2026-10-12)

**WIP.** The final capture runs on `main` once #828 (subpart appendices in the eCFR adapter) has merged; the
numbers below come from pre-captures with #828's code and are replaced by the final run's.

It also waits for the eCFR section-text fix (branch `fix/ecfr-section-text-breaks`, after #828), which makes section
bodies keep table captions and break words at `<br/>` as #828 does for appendices. Its impact run finds two part-416
sections change: 416.974 gains its table caption and "earningsaveraged" (in the locked body) becomes "earnings
averaged", and 416.1112 gains its table caption. Cutting one successor that carries both changes gives part 416 one
release swap and one rulespec-us re-pin instead of two, and keeps a later re-cut from starting at
`2026-09-11-title-20-part-416` and dropping the appendix. If the fix has not merged by 2026-10-13, the successor is cut
with #828 alone and this note records that the two sections still need it.

"Appendix to Subpart K of Part 416" (the list of types of income excluded under SSI by federal laws other than the
Social Security Act) is the one node of part 416 that no locked scope carries. The released
`us/regulation/2026-09-11-title-20-part-416` skipped it because `extract-ecfr --include-appendices` raised on
subpart-scoped identifiers (`docs/ingest-runs/2026-09-11-federal-cfr-followon-parts.md`). #828 lets the adapter take
it at `us/regulation/20/416/subpart-K/appendix`, a level-2 child of `us/regulation/20/416/subpart-K`.

Release validation needs every parent in the same scope, and a profiled release rejects a citation path that two
selected scopes carry, so the appendix cannot ship beside the released scope as a one-row scope. It ships in a
whole-part successor, `us/regulation/2026-10-12-with-appendices-title-20-part-416`, that replaces
`2026-09-11-title-20-part-416` in a release.

## Point in time: 2026-09-09, the released scope's

The released scope's version prefix is its run date. Its rows carry `source_as_of` and `expression_date` 2026-09-09:
on 2026-09-11 the Versioner API served title 20 only up to 2026-09-09. The successor uses the same point in time
(`--as-of 2026-09-09 --expression-date 2026-09-09`).

- eCFR `titles.json`, read 2026-10-12 17:44Z: title 20 `up_to_date_as_of` 2026-10-08, `latest_amended_on` and
  `latest_issue_date` 2026-09-30.
- The Versioner versions API (`versions/title-20.json?part=416`) lists part 416's latest issue and amendment date
  as 2026-04-03 (27 content versions issued that day); a query for `issue_date[gte]=2026-04-04` returns none. It
  lists the appendix with amendment date 2016-12-19 (substantive) and a non-substantive re-issue on 2023-03-30.
- The Versioner API still serves 2026-09-09. Pre-captures at both dates:

| as of | part XML sha256 | structure JSON sha256 | rows | section bodies differing from the locked scope |
| --- | --- | --- | ---: | ---: |
| 2026-09-09 | `11ec5a3f…1b26` (= locked) | `9587a2f1…1d55` (= locked) | 623 | 0 of 599 |
| 2026-10-08 | `11ec5a3f…1b26` (= locked) | `912fc424…f5d6cc` | 623 | 0 of 599 |

At 2026-10-08 the part XML is byte-identical and every body is unchanged; the title-wide structure JSON differs
because other parts of title 20 changed (the 2026-09-30 amendment), and every row's `source_as_of` and
`expression_date` would move to 2026-10-08. At 2026-09-09 both source files are byte-identical to the locked scope's,
so the successor adds one row and changes no other byte of row content. That is why 2026-09-09 was chosen; the text is
also what eCFR serves on 2026-10-08.

## Capture

```bash
B=data/corpus
uv run axiom-corpus-ingest inventory-ecfr --base $B --version 2026-10-12-with-appendices --as-of 2026-09-09 \
  --only-title 20 --only-part 416 --include-appendices
uv run axiom-corpus-ingest extract-ecfr --base $B --version 2026-10-12-with-appendices --as-of 2026-09-09 \
  --expression-date 2026-09-09 --only-title 20 --only-part 416 --include-appendices --workers 2
```

`ecfr_run_id` appends `title-20-part-416`, so the scope is `2026-10-12-with-appendices-title-20-part-416` (the
`<run date>-<qualifier>-title-N-part-M` shape of `2026-10-06-w6-federal-ecfr-closure-title-29-part-541`).

## Result against the locked 2026-09-11 scope

Compared row by row on `citation_path`, ignoring the fields that name the version (`version`, `source_path`; `id` and
`parent_id` derive from the path and are equal anyway):

- 623 rows: the 622 rows of `2026-09-11-title-20-part-416`, every field equal and in the same order, plus one.
- 599 sections compared, 0 bodies differ; 0 differences in any other field of any row.
- New row `us/regulation/20/416/subpart-K/appendix`: `kind` appendix, level 2, parent `us/regulation/20/416/subpart-K`,
  ordinal 1,000,000 (after the subpart's sections), legal identifier `20 CFR part 416, subpart K, appendix`, heading
  "List of Types of Income Excluded Under the SSI Program as Provided by Federal Laws Other Than the Social Security
  Act", body 22,582 characters in five categories (I Food, II Housing and Utilities, III Education and Employment,
  IV Native Americans, V Other).
- Text check, independent of the adapter: the word sequence of the appendix's `DIV9` in the source XML, less its
  `HEAD` and the bracketed `CITA` source note, equals the body's (3,952 words). #828's later commit b62d21832
  (words separated at block boundaries) leaves this body byte-identical.

## The wave-5 manifest for the same path is retired

#718 wrote `manifests/us-ecfr-title-20-part-416-appendix-k-2026-09-15.yaml` (scope
`2026-09-15-title-20-part-416-appendix-k`), which took the appendix from the eCFR renderer API as an official HTML
document at `us/regulation/20/416/subpart-K/appendix` plus `.../appendix/block-1`. It was never signed or locked:
no lock or ingest manifest names it, and #718 locked none of its eight scopes. Left in place, a later pass over the
wave-5 Controller list could lock it, and two scopes would carry the appendix path. This PR removes it:

- deletes the manifest, and the `ssi-cfr-416-appendix-k` family from
  `scripts/build_federal_guidance_layer_manifests.py` (the five other families regenerate their manifests
  byte-identically);
- points the SSI queue's eCFR row at the successor (`target_scope`, `index_document_count` and `taken_count` 623)
  and drops its `appendix_subpart_k_scope` record;
- marks the scope retired in `docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md`, at the appendix bullet and in its
  Controller list.

The needs-closure snapshots (`docs/coverage/needs-closure-2026-09-1{1,4}/`) and the wave-5 decisions CSV are dated
records and are left as they were.

Impact of the generator edit, checked by hand (the GitNexus index here fails to open: storage version 42, build 40):
`build_ssi_cfr_416_appendix_k`, `APPENDIX_K_VERSION` and `ECFR_APPENDIX_*` are referenced only inside the script; no
module imports it and no test covers it. `ruff check` passes; `mypy` reports the same 17 pre-existing errors before and
after.

## Citation-path ratchets

Measured with `scripts/validate_citation_paths.py` over every locked provisions file on `main` (2,330, fetched with
`corpus fetch --path data/corpus/provisions`): `main` alone measures exactly at the baselines. With the new file the
only change is `uppercase_segments` 18,796 to 18,797: the one new unique path, `us/regulation/20/416/subpart-K/appendix`
(eCFR's subpart letter). Its other 622 paths are already counted through the locked scope. No identity drift.

## Release hand-off

For the Axiom eng hub: select `us/regulation/2026-10-12-with-appendices-title-20-part-416` in place of
`us/regulation/2026-09-11-title-20-part-416`, never both. Seven selectors under `manifests/releases/` name the old
scope (`us-rulespec-2026-09-13-cms-state-plans-union` through `us-rulespec-2026-10-11-w5-remainder-union`), and so
does the open #819 (`us-rulespec-2026-10-12-w6-successor-union`). Release cutting, activation and rulespec-us re-pins
are not part of this PR.

## Checks

TBD with the final capture: coverage, signed ingest manifest, lock, push, ratchet re-measure, focused tests.
