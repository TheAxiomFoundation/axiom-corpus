# Federal proposal-security authority corpus ingest

This scope supplies the primary federal and NSF sources needed for proposal-stage
security and submission checks. It deliberately excludes general award
administration, cost principles, post-award Part 170 reporting,
debarment/suspension, and the institution-of-higher-education-only authorities in
42 U.S.C. 19039-19040. PAPPG 24-1 Chapters II-III, NSF 26-506 (PESOSE) and the
2 CFR Part 200 slice are held by `us/guidance/2026-09-24-nsf-pappg-pesose` and
`us/regulation/2026-09-24-nsf-slice-title-2-part-200` (axiom-corpus#631), not here.

The sources were captured on 2026-08-30. On 2026-09-28/29 the five scopes were
rebuilt on `main` with its current adapters (axiom-corpus#636, previously stacked on
the unmerged #635): the two U.S. Code scopes were re-extracted from the same retained
release-point zips with `extract-usc --source-zip` and made self-contained, and the
eCFR and NSF scopes were regenerated and compared with the 2026-08-30 artifacts
(identical; see "Regeneration on main").

| Scope | Rows |
| --- | ---: |
| `us/statute/2026-08-30-proposal-security-title-31` (31 U.S.C. 1352) | 72 |
| `us/statute/2026-08-30-proposal-security-title-42` (42 U.S.C. 1862o, 6605, 19231-19235, 19237) | 132 |
| `us/regulation/2026-08-30-proposal-security-title-2-part-25` (2 CFR Part 25, including Appendix A) | 16 |
| `us/regulation/2026-08-30-proposal-security-title-45-part-604` (45 CFR Part 604, including Appendices A-B) | 22 |
| `us/guidance/2026-08-30-federal-proposal-security-guidance` (six NSF documents, 19 scoped blocks) | 25 |

Every scope: coverage complete (source rows = provision rows, 0 missing, 0 extra),
every parent link resolves inside the scope, and each scope carries a signed ingest
manifest under `.axiom/ingest-manifests/us/<class>/<version>.json`.

## Immutable federal sources

The U.S. Code source is the OLRC release point `Online@119-102`, current through
Public Law 119-102 (July 12, 2026).

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `xml_usc31@119-102.zip` | 1,305,746 | `1cccbcc7e0fe4bc548b970e866dced83a728bca2f3d305f477405f0426735b78` |
| ZIP member `usc31.xml` | 8,753,617 | `254572a738146d41174b64232c98f630e892b8d368d7a1841d3750d8cb102185` |
| `xml_usc42@119-102.zip` | 18,161,570 | `31929c28f117362ac8788607242795769b05ed7726f07e4ed3b1786f39655ce7` |
| ZIP member `usc42.xml` | 113,732,787 | `b72955590abe55bdbd1ce5d13c5293955a82add9c84fad92c1674ec469e86624` |

Official downloads:

- `https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc31@119-102.zip`
- `https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc42@119-102.zip`

Both zips were downloaded again from these URLs at 2026-09-29T02:49Z and are
byte-identical to the retained files. Each scope retains its zip byte-for-byte under
`sources/us/statute/<scope>/olrc/` as its only source file: every inventory item and
provision row has `source_path` pointing at the zip, the inventory `sha256` equal to
the zip's, and `metadata.source_archive_member` naming the member parsed in memory
(the `extract-usc --source-zip` convention of `docs/ingest-runs/2026-09-13-federal-statute-layer.md`).
The 113 MB Title 42 member exceeds GitHub's 100 MB per-file limit, so it is recoverable
from the retained 18 MB zip rather than tracked uncompressed.

The eCFR source date is August 27, 2026, which the 2026-08-30 capture recorded as the
newest version the eCFR versioner API then exposed.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Title 2 Part 25 XML | 18,189 | `6afb0be190a4b937ee1cffd49ffdff1289554225fb5c6acb26ba560cf8ffc52d` |
| Title 2 structure JSON | 1,349,222 | `8be0489b8a14aa1f821de4415caf8103f8bf943614bb473189094225a590be76` |
| Title 45 Part 604 XML | 36,211 | `c0adf8b08dff971b06984817826cbe7e94db190c9c36ae32724fee72c0ba2323` |
| Title 45 structure JSON | 4,107,005 | `aa178d9c9dc8410832f32d9b275f522ec28283b6af68f9d56b2b341f64ed4185` |

Part 604 Appendix B's official SF-LLL form is image-only. The adapter archived all
three Federal Register PNG renditions, and the `appendix-b` row's body references
each one:

| Graphic | Bytes | SHA-256 |
| --- | ---: | --- |
| `EC01JA91.007.png` | 4,121 | `8fe4e55182918231b96bb881d20dc5ccfb97865b2037a2fe3a6cfdd68cf050ff` |
| `EC01JA91.008.png` | 8,087 | `03394bcac854e8e8a7de7124d10faafbc04e2ef80a02760d06300305742e1ec1` |
| `EC01JA91.009.png` | 688 | `cf1ebd4003cd8e54e4e6e252fb06e7062d096bca62f50b780f3fb74ec06a107c` |

## NSF implementation sources

`manifests/us-federal-proposal-security-2026.yaml` extracts only the operative
proposal-security ranges:

- PAPPG 24-1 Chapter I.G.1-G.2 (duplicate/substantially similar proposals,
  lead UEI/SAM, and named-subrecipient UEI/Research.gov setup);
- Supplement 1 sections 5 and 12 (DMSP and research security);
- Supplement 2 section 3 (the current DMSP workflow, including the April 27,
  2026 Research.gov tool transition);
- Important Notice 149 items 1-4;
- all nine implementation FAQ questions; and
- the NSF TIP person/entity-of-concern implementation page.

| Captured page (2026-08-30) | Bytes | SHA-256 |
| --- | ---: | --- |
| `nsf-pappg-24-1-chapter-i-submission-security.html` | 108,260 | `a8f98d21d424ab919458571a268b50c77f7c42164fecfb4bdbe3a94c64197d29` |
| `nsf-pappg-24-1-supplement-1-proposal-security.html` | 86,111 | `688a2d3e8bfb947a983719f1ed6c40109b2345c7264cb3ce677a121458add801` |
| `nsf-pappg-24-1-supplement-2-dmsp.html` | 73,821 | `4dfd5d291ec92dc9102ce102fa25534ac870eed47d11c6d2b0ab844ddf05c119` |
| `nsf-important-notice-149-proposal-security.html` | 78,474 | `b80a6a59dbb102e3371b4eab6e90971562e91e551220c892533b2efb3da9cb8d` |
| `nsf-important-notice-149-implementation-faq.html` | 68,983 | `a80e70b6640477ae3f95cc9a54b394a03aac087d1d17e7ff6fb50c774f5fdf41` |
| `nsf-tip-person-entity-of-concern-prohibition.html` | 54,758 | `161ff22863b12f79cdc783b7bd8a265909b98899a0e79bacbb6ceff4e8d56275` |

The supplement source HTML remains intact. The supplements mark revisions inline
("underlined text is added and strikes previous text"); normalized effective-policy
text drops only the struck HTML `s` elements and keeps the underlined replacement
text. The TIP page is tagged `dynamic_external_lists` and
`prohibited_entity_names_must_not_be_encoded`: entity names from its linked live lists
must not be encoded into RuleSpec. The single-block TIP page uses the semantic leaf
`implementation` rather than a synthetic `block-N` path.

## Adapter commands

`extract-usc` appends `-title-<n>` to `--version` (`usc_run_id`), and `extract-ecfr`
appends `-title-<n>-part-<p>`.

```bash
B=data/corpus
V=2026-08-30-proposal-security

uv run axiom-corpus-ingest extract-usc --base $B --version $V \
  --source-zip xml_usc31@119-102.zip --title 31 \
  --source-as-of 2026-07-12 --expression-date 2026-07-12 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc31@119-102.zip \
  --section 1352

uv run axiom-corpus-ingest extract-usc --base $B --version $V \
  --source-zip xml_usc42@119-102.zip --title 42 \
  --source-as-of 2026-07-12 --expression-date 2026-07-12 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc42@119-102.zip \
  --section 1862o --section 6605 --section 19231 --section 19232 \
  --section 19233 --section 19234 --section 19235 --section 19237

uv run python scripts/self_contain_usc_scope.py --base $B \
  --version $V-title-31 --version $V-title-42

uv run axiom-corpus-ingest extract-ecfr --base $B --version $V \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 2 --only-part 25 --include-appendices --workers 1

uv run axiom-corpus-ingest extract-ecfr --base $B --version $V \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices --workers 1

uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-08-30-federal-proposal-security-guidance \
  --manifest manifests/us-federal-proposal-security-2026.yaml
```

`--source-as-of`/`--expression-date` 2026-07-12 is the release point's currency date,
the convention of the other retained-zip U.S. Code scopes; each member's XML creation
date (2026-05-04 for Title 31, 2026-07-23 for Title 42) is in every row's
`metadata.created_date`.

## Self-containment

`us/statute/42` is already carried by the released
`us/statute/2026-07-19-rulespec-title-42-consolidated`, and a release selector cannot
carry a citation path twice (`duplicate_release_citation` is an error). The 2026-08-30
build included the title rows (`--include-title`), so its Title 42 scope collided with
the `us-rulespec-2026-09-14-wave4-r2-union` selection on `us/statute/42`. The rebuild
follows `docs/ingest-runs/2026-09-13-federal-statute-layer.md` instead: no title row,
and `scripts/self_contain_usc_scope.py` detaches each section row's out-of-scope parent
(`parent_citation_path`/`parent_id` cleared, `metadata.self_contained_root: true`,
`metadata.detached_parent_citation_path: us/statute/<title>`). No scope carries
`us/statute/31`; Title 31 follows the same shape so a later Title 31 scope can carry
the title row without a collision. Detached roots: 1 (Title 31) and 8 (Title 42), one
per section. Row counts per section: 1352 72; 1862o 3, 6605 39, 19231 10, 19232 13,
19233 12, 19234 18, 19235 4, 19237 33.

## Regeneration on main

- **U.S. Code.** Against the 2026-08-30 artifacts, the rebuilt rows have the same
  citation paths (less the two title rows) and identical headings and bodies. Only
  metadata changed: main's adapter records `source_format: uslm-xml` and
  `metadata.source_archive_member`, where #635's unmerged adapter recorded
  `uslm-xml+zip`, `archive_member`, `archive_member_sha256` and `archive_sha256`; and
  the section rows are detached roots.
- **eCFR.** Re-running both `extract-ecfr` commands above live on 2026-09-29 produced
  source, inventory, provisions and coverage files byte-identical to the 2026-08-30
  artifacts. Main needs `--include-appendices` for the appendix rows (axiom-corpus#634).
- **NSF.** An offline replay of the manifest with `local_path` pointed at the six
  retained captures produced byte-identical sources and coverage; the inventory and
  provision rows are identical once the two replay-only fields are restored
  (`download_url`, which a local replay records as a `file://` path, and
  `content_type`, which it records as null). The retained 2026-08-30 artifacts are
  therefore the output of main's extractor on the captured bytes.

## Currency checks (2026-09-29)

- **U.S. Code.** The current release point is Public Law 119-111 (09/18/2026) per
  `https://uscode.house.gov/download/download.shtml`. Extracting the same sections
  from `xml_usc31@119-111.zip` (SHA-256
  `c49c36893cc350fea84d458645c95e6883fe8c7b927976913e86b452e6a5df4d`) and
  `xml_usc42@119-111.zip` (SHA-256
  `d2df95e45d3bc365a4bfcbeb346e6a828abd7f41bfd8915be3600112a29d7a01`) gives the same
  72 and 132 citation paths with identical headings, bodies, kinds and parents, so the
  119-102 text is also the current text. Rows keep the default prelim reader
  `source_url`; `--prior-release-point` is not needed.
- **eCFR.** The versioner API reports the latest amendment of 2 CFR Part 25 as
  2024-10-01 and of 45 CFR Part 604 as 2016-09-12, with both titles up to date as of
  2026-09-25, so the 2026-08-27 text is current.
- **NSF.** A live `extract-official-documents` run at 2026-09-29T02:51Z yields the same
  25 citation paths with identical headings and bodies. The live HTML bytes differ from
  the captures (page chrome), so the 2026-08-30 captures stay the retained sources.

## Citation-path grammar

The five scopes add 110 unique uppercase citation paths: 100 U.S. Code subparagraph
letters and 10 eCFR subpart labels (`us/regulation/2/25/subpart-A` to `subpart-D`,
`us/regulation/45/604/subpart-A` to `subpart-F`). The `uppercase_segments` ratchet in
`schema/citation-path.v1.json` is raised from main's 16,281 to 16,391, and
`scripts/validate_citation_paths.py` passes. Other branches that raise this ceiling
will conflict on that line; recompute it on merge.

## Release validation

| Selector (scratch, not tracked) | Scopes | Result |
| --- | ---: | --- |
| the five scopes, `--strict-warnings` | 5 | `ok: true`, 0 errors, 0 warnings |
| `us-rulespec-2026-09-14-wave4-r2-union` plus the five scopes, `--ignore-r2-missing` | 1,047 | `ok: true`, 0 errors, 546 warnings, none naming these scopes |

The 546 warnings are the pre-existing 541 `missing_parent_id` and 5
`unsectioned_document_body` recorded in `docs/ingest-runs/2026-09-23-tax-statute-policybench.md`.
None of the 267 citation paths is carried by any scope of that union selector.

## Signing

The artifacts were force-added (`data/` is gitignored) and committed, then each scope
was signed against that clean commit with `axiom-corpus-ingest sign-ingest-manifest`,
recording the rebuild command above. `tests/test_federal_proposal_security_manifest.py`
checks that each manifest attests exactly the scope's artifacts at their committed
SHA-256, and verifies the signatures when `AXIOM_CORPUS_INGEST_PUBLIC_KEY` is set.

No R2 synchronization, release selector, publication, Supabase load, production
activation, or deployment was performed.
