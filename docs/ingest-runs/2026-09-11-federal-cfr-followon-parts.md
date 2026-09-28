# Federal CFR follow-on parts: 45 CFR 98, 42 CFR 436, 20 CFR 416 (2026-09-11)

Follow-on to the 2026-09-10 program ingestion. The CCDF, Medicaid and SSI runs each found a
federal regulation family that was inventoried but not taken (`2026-09-10-ccdf-state-plans-fy2025-2027.md`,
`2026-09-10-medicaid-state-eligibility-manuals-batch-1.md`, the SSI federal queue row). This run
takes the three families as complete-coverage eCFR scopes. Everything here is local and unsigned:
the artifacts are under `data/corpus` on the controller's machine only (`data/` is gitignored) and
nothing under `data/corpus` is committed on this branch.

Branch: `discovery/ingest-federal-cfr-followon`, cut from `origin/discovery/program-ingestion-union`,
worked in a sparse worktree (`~/axiom-corpus-worktrees/federal-cfr`, `data/corpus` excluded) with
every extraction pointed at `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`. GitNexus MCP
tools were not available in this session, so the impact analysis CLAUDE.md asks for before editing
`src/axiom_corpus/corpus/ecfr.py` was done by hand (see "Adapter fix").

| Scope (`us/regulation`) | eCFR units | Rows | Sections | Coverage | Extract |
| --- | ---: | ---: | ---: | --- | ---: |
| `2026-09-11-title-45-part-98` | 73 | 73 | 61 | complete, 0 missing, 0 extra | 2 s |
| `2026-09-11-title-42-part-436` | 87 | 87 | 75 | complete, 0 missing, 0 extra | 2 s |
| `2026-09-11-title-20-part-416` | 622 | 622 | 599 | complete, 0 missing, 0 extra | 6 s |

Publisher: eCFR Versioner API only (`https://www.ecfr.gov/api/versioner/v1/`), the same primary
publisher as the released `2026-06-25-title-42-part-435`, `2026-06-24-title-45-part-1302` and
`2026-06-15-title-7-part-275` scopes. No Cornell LII or other republication was consulted.

## Source date

The API serves title structure and full XML only up to each title's `up_to_date_as_of`, which was
2026-09-09 for titles 20, 42 and 45 on 2026-09-11 (`titles.json`: title 20 latest amended
2026-09-09, title 42 2026-08-13, title 45 2026-08-31). A request for 2026-09-10 answers
"past the title's most recent issue date". All three scopes therefore use `--as-of 2026-09-09
--expression-date 2026-09-09`, the same convention the 1302 precedent recorded (requested
2026-06-24, served 2026-06-22). The corpus version prefix is the run date, 2026-09-11.

## Adapter fix: eCFR full-XML endpoint now requires response compression

The first `extract-ecfr` attempt (45 CFR 98) failed after 122 s with
`45 CFR: HTTP Error 406: Not Acceptable` and wrote an empty scope (73 missing). The response
body is the publisher's own API contract, not a bot wall:

```xml
<error>
  <message>This endpoint requires response compression. Send an Accept-Encoding header that permits compression.</message>
  <supportCode>11</supportCode>
</error>
```

Every date and part probed (2026-07-14 through 2026-09-09; parts 98, 436, 416) answers 406 to
`fetch_ecfr_part_xml`'s plain `urllib` request, and 200 with `Content-Encoding: gzip` as soon as
the request carries `Accept-Encoding: gzip`. The structure and versions endpoints still answer
200 uncompressed. The July 416 slice and the June precedents ran before this requirement existed.

Change (`src/axiom_corpus/corpus/ecfr.py`): the three Versioner fetchers
(`fetch_ecfr_structure`, `fetch_ecfr_title_xml`, `fetch_ecfr_part_xml`) now go through
`_fetch_ecfr_api_bytes`, which sends `Accept-Encoding: gzip, deflate` and decodes the reply by
its `Content-Encoding` (`_decode_content_encoding`; identity passes through, anything else
raises). Signatures are unchanged. Hand impact analysis: the only callers are
`build_ecfr_inventory` (structure) and the per-title worker in `extract_ecfr` (part or title XML)
inside `ecfr.py`, both behind `_fetch_bytes_with_retries`; every test in
`tests/test_corpus_ecfr.py` monkeypatches the fetchers wholesale, so they are unaffected;
`scripts/repro_us_cfr_416_deeming_slice.py` reads retained snapshots only. Two unit tests cover the
header and gzip decoding and the unsupported-encoding rejection. `mypy` and `ruff check` pass on
the module; `docs/corpus-pipeline.md` records the requirement.

## Part 98: Child Care and Development Fund (45 CFR)

- Scope `us/regulation/2026-09-11-title-45-part-98`, citation paths `us/regulation/45/98`,
  `.../subpart-A` to `.../subpart-K`, `.../<section>` (61 sections, 98.1 to 98.105).
- eCFR structure 2026-09-09: 1 part, 11 subparts (A to K), 61 sections, no reserved node, no
  appendix, no subject groups. 73 units; 73 rows; 73/73 matched.
- Bodies: every section body non-empty (170 to 14,236 characters; 229,361 in total). The 12
  container rows (part and subparts) have empty bodies, the same shape as the released 435 scope
  (15 empty container rows) and 1302 scope.
- Overlap: no provisions file under `data/corpus/provisions` (any jurisdiction) carries a
  `us/regulation/45/98` path; no coverage file, manifest or run note mentions part 98. Nothing to
  supersede.
- Sources (`sources/us/regulation/2026-09-11-title-45-part-98/ecfr/`, 4.2 MB):
  `title-45-part-98.xml` 264,446 bytes sha256 `db0f223a13a8c0df5ad18ae142f66dfe80db34aba8330d5461ed9f9cb8b52310`
  from `full/2026-09-09/title-45.xml?part=98`; `title-45.structure.json` 4,100,791 bytes sha256
  `9ee8b602c32b892fcd5a2780ed1cd9e14e8ec7f4d96bbc6477cc11a776905a81` from `structure/2026-09-09/title-45.json`.
- Timing: `inventory-ecfr` 7 s; `extract-ecfr` 122 s failed (406, before the fix), then 2 s.

## Part 436: Medicaid eligibility in Guam, Puerto Rico and the Virgin Islands (42 CFR)

- Scope `us/regulation/2026-09-11-title-42-part-436`, citation paths `us/regulation/42/436`,
  `.../subpart-A` to `.../subpart-L` except H, `.../<section>` (75 sections, 436.1 to 436.1102).
- eCFR structure 2026-09-09: 1 part, 12 subparts of which H is reserved, 75 live sections plus 3
  reserved (`436.402`, `436.408`, `436.604-436.608`), 12 subject-group headings. The adapter skips
  reserved nodes and does not emit subject groups (the released 435 scope has the same shape), so
  87 units; 87 rows; 87/87 matched.
- Bodies: every section body non-empty (68 to 25,837 characters; 115,341 in total; the short ones
  are one-sentence "Scope" sections such as 436.100, 436.200, 436.300). 12 empty container rows.
- Overlap: no provisions file carries a `us/regulation/42/436` path. Part 435 stays in the released
  `2026-06-25-title-42-part-435` and the CMS-2454-IFC scopes; part 436 shares no path with them.
- Sources (`.../2026-09-11-title-42-part-436/ecfr/`, 5.1 MB): `title-42-part-436.xml` 155,671 bytes
  sha256 `ae8612a1b04f9d397cf351ddf2227ab95bb2732bc1e873e9a781f49f0a4fb56f`;
  `title-42.structure.json` 5,157,493 bytes sha256 `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed`.
- Timing: `inventory-ecfr` 2 s; `extract-ecfr` 2 s.

## Part 416: Supplemental Security Income (20 CFR)

- Scope `us/regulation/2026-09-11-title-20-part-416`, citation paths `us/regulation/20/416`,
  `.../subpart-A` to `.../subpart-V`, `.../<section>` (599 sections, 416.101 to 416.2227).
- eCFR structure 2026-09-09: 1 part, 22 subparts, 599 live sections plus 8 reserved (`416.908`,
  `416.928`, `416.992a`, `416.1465`, `416.1466`, `416.1720-416.1725`, `416.2206`, `416.2218`),
  73 subject groups, and one appendix, "Appendix to Subpart K of Part 416" (list of income types
  excluded under federal laws other than the Social Security Act). 622 units; 622 rows; 622/622
  matched. This is the same 622-unit count the 2026-07-23 slice note recorded.
- The Subpart K appendix is not taken: `--include-appendices` only accepts part-scoped
  `Appendix X to Part NNN` identifiers and raises on this subpart-scoped one, so the run mirrors
  the July slice and the June precedents (no appendices). Follow-up: extend
  `_appendix_citation_from_identifier` to subpart appendices, then re-take with `--include-appendices`.
- Bodies: every section body non-empty (74 to 54,327 characters; 1,396,584 in total). 23 empty
  container rows.
- Sources (`.../2026-09-11-title-20-part-416/ecfr/`, 5.5 MB): `title-20-part-416.xml` 1,745,553
  bytes sha256 `11ec5a3f11457ebdca99bc958c9666740590a544cd44bd88e681f29b9bf41b26`;
  `title-20.structure.json` 3,981,872 bytes sha256 `9587a2f15038535028f87ccbe8d81318db2cf2f7e1abdf781e41ece2da3d1d55`.
  The part XML is byte-identical to the July slice's 2026-07-14 snapshot (same sha256), so title
  20's 2026-09-09 amendment did not touch part 416.
- Timing: `inventory-ecfr` 1 s; `extract-ecfr` 6 s.

### How the 416 overlap was resolved

The premise that the released corpus already carries part of 20 CFR 416 does not hold:

- The only sibling is `us/regulation/2026-07-23-title-20-part-416`, the explicit 14-row deeming
  slice (part, subparts K, L and R, sections 416.1149, .1160, .1161, .1163, .1167, .1202, .1207,
  .1801, .1802, .1806). It has a signed ingest manifest on `main`
  (`.axiom/ingest-manifests/us/regulation/2026-07-23-title-20-part-416.json`, commit `660fff91`
  on `ingest/cfr-416-deeming`) but no selector under `manifests/releases/` names it, the released
  `us-rulespec-2026-08-23-canada-338-suspension-union` does not carry it, and neither does the
  draft `2026-09-11-us-rulespec-program-ingestion-union.selector.json`.
- The SSI title XVI work is statute (`us/statute/2026-06-20-ssi-title-xvi-title-42-...`, 42
  U.S.C. 1381 et seq.); it shares no citation path with `us/regulation/20/416`.
- A grep of every provisions JSONL under `data/corpus/provisions` for `us/regulation/20/416`
  finds only the July slice and the new scope.

So the "subparts not yet released" option collapses to the whole part, and the choice is the
full-part scope with no consolidation and no selector swap: released scopes are untouched, the
slice stays on disk, signed and unselected, exactly as it is today. The two 416 scopes are
mutually exclusive in any selector (all 14 slice paths recur in the full part), so a selector
must never carry both; the full part is the one to select. Text check on the ten slice sections
against the new scope: seven byte-equal; 416.1163, 416.1167 and 416.1207 differ only because the
current adapter renders the `Example N.` headings as their own lines (the source XML is
identical), so the new text is a superset. The four slice container rows carried bodies
materialized from their selected descendants; the standard adapter leaves container bodies
empty, as in every other released eCFR scope.

Version name: the run id is `2026-09-11-title-20-part-416`, without the `-<qualifier>` suffix
the work order suggested, because `ecfr_run_id` appends `title-20-part-416` to `--version` and a
qualifier could only sit before it (`2026-09-11-full-title-20-part-416`), inconsistent with the
other two scopes and with the precedents. The date already separates it from the July slice.
Re-extracting under another name costs 6 s if the controller prefers a qualifier.

## Draft selector validation

Draft = `docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json` plus the
three scopes (539 scopes; nothing removed), built in the session scratch directory and validated
from the worktree:

```bash
uv run axiom-corpus-ingest validate-release \
  --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release <scratch>/draft-federal-cfr.selector.json \
  --ignore-r2-missing --max-issues 50
```

Result: `ok: true`, `error_count: 0`, `warning_count: 546`, 50 s. With `--max-issues 600` the
546 warnings are exactly the consolidation note's set: 541 `missing_parent_id` in
`us-ca/regulation/2026-07-13-recovery` and 5 advisory `unsectioned_document_body` (4 in
`2026-09-10-wic-state-policy-manual`, 1 in `2026-09-10-tax-state-forms-ty2025`). No issue names
a `2026-09-11-title-*` scope; no `duplicate_release_citation`.

## Queue rows

One `agent_ready` row per program queue, inserted after the existing federal row, mirroring the
Medicaid federal row's `source_kind: federal_regulation_ecfr` shape with `target_manifest: null`
(eCFR runs are not manifest-driven), `target_scope` the new version, `index_url` the structure JSON
that certifies the unit count, `index_document_count` the unit count and `taken_count` the rows.
The existing federal rows' notes gain a one-sentence pointer. `status_counts` recomputed the way
the builder scripts do (CCDF agent_ready 44 to 45, Medicaid 41 to 42, SSI 28 to 29). Files
round-trip byte-identically through `yaml.safe_dump(sort_keys=False, allow_unicode=True, width=120)`.

## Commands

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
for tp in "45 98" "42 436" "20 416"; do set -- $tp
  uv run axiom-corpus-ingest inventory-ecfr --base $B --version 2026-09-11 --as-of 2026-09-09 \
    --only-title $1 --only-part $2
  uv run axiom-corpus-ingest extract-ecfr --base $B --version 2026-09-11 --as-of 2026-09-09 \
    --expression-date 2026-09-09 --only-title $1 --only-part $2 --workers 2
done
```

Disk: 7.0 GB free at start, 6.4 GB after the worktree venv and the three scopes (15 MB of sources).

## Checks

- `uv run ruff check scripts`: passes. `ruff check` and `mypy` on the changed module and test file:
  pass. (`ruff format --check` would reformat `ecfr.py` and `test_corpus_ecfr.py`, but it already
  would on the unpatched files; the repository gate is `ruff check`, so no reformat was applied.)
- `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery or ecfr"`
  in the sparse worktree: 438 passed, 2 skipped, 21 failed, 62 s. The same selection in the main
  checkout (which has `data/corpus`) passes with 0 failures, so all 21 are the sparse-worktree
  artifact the gotchas note describes (`FileNotFoundError` on retained `data/corpus` sources), not
  regressions: the note's ten (`test_be_rulespec_2026_08_23_promotion`, two in
  `test_build_ny_tanf_compatibility_scope`, `test_rulespec_be_source_promotion`, AK, CT, MI, MT, ND,
  NY SNAP manual tests) plus eleven more pulled in by the wider `ecfr` keyword or added since the
  note: seven in `test_corpus_ecfr.py` (`test_retained_416_default_scope_ignores_unsupported_appendix`
  x6 and `test_iter_ecfr_title_provisions_preserves_mixed_part_parentage_and_bodies`, which open
  the retained 2026-07-23 416 and 2026-06-24 1302 snapshots), two `test_recover_ingest`
  `ecfr-xml` parametrizations (retained 275 and 1302 XML), `test_armenia_arlis`
  `test_checked_in_tax_code_2024_continuity_sources_match_manifest` and `test_israel_openlaw`
  `test_pilot_manifest_pins_all_three_instruments`.

## Controller

Selector additions (no swaps; no released scope superseded; no unreleased scope dropped):

```json
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-11-title-45-part-98"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-11-title-42-part-436"},
{"document_class": "regulation", "jurisdiction": "us", "version": "2026-09-11-title-20-part-416"}
```

1. Merge this branch with the program branches (it is cut from the union and touches only
   `ecfr.py`, its tests, the three queues, two changelog fragments and docs). The adapter fix is
   required for any future `extract-ecfr` run.
2. Add the three entries to the draft union selector (536 to 539 scopes) and re-run
   `validate-release --ignore-r2-missing`; expect `ok: true`, 0 errors, 546 warnings.
3. Do not add `us/regulation/2026-07-23-title-20-part-416` to the same selector.
4. Sign with `scripts/sign_release_scopes.sh` as the hand-off note describes; the three scopes add
   15 MB of sources and 2.5 MB of provisions to the artifact commit.
5. Optional follow-up: subpart-scoped appendix support in the eCFR adapter, then re-take the 416
   Subpart K appendix in a successor scope.
