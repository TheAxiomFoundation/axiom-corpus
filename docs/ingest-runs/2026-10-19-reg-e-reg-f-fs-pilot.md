# Regulation E and Regulation F: 12 CFR 1005 and 1006 (2026-10-19)

First Title 12 CFR text in the corpus. It feeds a capped financial-services
encoder pilot: three sections (12 CFR 1005.6, 1005.11 and 1006.14), run to
measure the encoder's success rate on consumer-finance rules that apply to
customer-facing AI agents. No provisions file under `data/corpus/provisions`
carried a `us/regulation/12/` path before this run, so nothing is superseded.

| Scope (`us/regulation`) | eCFR units | Rows | Sections | Coverage | Extract |
| --- | ---: | ---: | ---: | --- | ---: |
| `2026-10-19-title-12-part-1005` | 30 | 30 | 27 | complete, 30/30 matched | 3 s |
| `2026-10-19-title-12-part-1006` | 19 | 19 | 15 | complete, 19/19 matched | 3 s |

Publisher: eCFR Versioner API only (`https://www.ecfr.gov/api/versioner/v1/`), the
same primary publisher as the released 7, 20, 42 and 45 CFR scopes.

## Commands

```bash
for p in 1005 1006; do
  uv run axiom-corpus-ingest inventory-ecfr --base data/corpus --version 2026-10-19 \
    --as-of 2026-10-16 --only-title 12 --only-part "$p"
  uv run axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-10-19 \
    --as-of 2026-10-16 --expression-date 2026-10-16 --only-title 12 --only-part "$p"
done
```

## Source date

eCFR `titles.json` (read 2026-10-19): title 12 `up_to_date_as_of` 2026-10-16,
`latest_issue_date` 2026-10-05, `latest_amended_on` 2026-10-02. Both scopes use
`--as-of 2026-10-16 --expression-date 2026-10-16`, the convention of the
2026-09-11 follow-on parts run (as-of and expression date equal to the title's
`up_to_date_as_of`). The version prefix is the run date.

## Part 1005: Electronic Fund Transfers (Regulation E)

- Citation paths `us/regulation/12/1005`, `.../subpart-A` (general, 1005.1 to
  1005.20), `.../subpart-B` (remittance transfers, 1005.30 to 1005.36),
  `.../<section>`.
- eCFR structure 2026-10-16: 1 part, 2 subparts, 27 sections; 30 units, 30 rows.
- Section bodies are all non-empty: 125 to 63,334 characters, 218,787 in total.
  The three container rows have empty bodies, the shape of the released 435,
  1302 and 98 scopes.
- Pilot targets: 1005.6 (consumer liability for unauthorized transfers;
  3,676 characters; carries the $50 and $500 tiers and the 60-day statement
  rule) and 1005.11 (error resolution; 7,636 characters; carries the 10
  business-day and 45-day clocks). 1005.2 (definitions, 6,446 characters) is
  in scope as context.
- Sources (`sources/us/regulation/2026-10-19-title-12-part-1005/ecfr/`):
  `title-12-part-1005.xml` 859,423 bytes sha256
  `0669a14f83f836f4086de21514f3bcd40041784e50c444b415f4d8e1909a10d0` from
  `full/2026-10-16/title-12.xml?part=1005`; `title-12.structure.json`
  4,945,031 bytes sha256
  `10fdae647d581e0b85ed1c824720ffd3b39e4c6a09f8a8120e353182d992266d` from
  `structure/2026-10-16/title-12.json`.

## Part 1006: Debt Collection Practices (Regulation F)

- Citation paths `us/regulation/12/1006`, `.../subpart-A`, `.../subpart-B`,
  `.../subpart-D`, `.../<section>`. Subpart C is reserved and the adapter skips
  reserved nodes.
- eCFR structure 2026-10-16: 1 part, 3 live subparts plus 1 reserved, 15
  sections; 19 units, 19 rows.
- Section bodies are all non-empty: 565 to 15,801 characters, 59,684 in total.
- Pilot target: 1006.14 (harassing, oppressive or abusive conduct; 5,160
  characters; carries the (b)(2) telephone-call frequency presumptions, "More
  than seven times within seven consecutive days"). 1006.2 (definitions, 5,738
  characters) is in scope as context.
- Sources (`sources/us/regulation/2026-10-19-title-12-part-1006/ecfr/`):
  `title-12-part-1006.xml` 231,338 bytes sha256
  `9138aa90547a14dac979a600a2f057f1005a5a90b74b1f4837e1ae1063f02432` from
  `full/2026-10-16/title-12.xml?part=1006`; the same `title-12.structure.json`
  as part 1005.

## Not taken

- **The appendices.** Part 1005: Appendix A (model disclosure clauses and
  forms), Appendix B (reserved), Appendix C (issuance of official
  interpretations). Part 1006: Appendix A (procedures for state application for
  exemption from the Act), Appendix B (model forms), Appendix C (issuance of
  advisory opinions). The three pilot targets do not cite them.
- **Supplement I to Parts 1005 and 1006** (the CFPB's official interpretations).
  `inventory-ecfr --include-appendices` raises `unsupported nonreserved eCFR
  appendix identifier: 'Supplement I to Part 1005'` (and the same for 1006): the
  adapter accepts only `Appendix X to Part N` identifiers. The interpretations
  bear on the current targets, not only on later work: the retained part 1006 XML
  carries comments to 1006.14, including (b)(2) itself and what counts as a
  telephone call (ringless voicemail), and Supplement I to part 1005 carries the
  comments to 1005.6 and 1005.11. These scopes are complete for the selected
  sections; taking the interpretations needs an adapter change and is a
  follow-up, not part of this run.

## Checks

- `scripts/validate_citation_paths.py` over the full fetched provisions tree
  (675,518 records, 517,342 unique paths): the two scopes add five unique paths
  with uppercase segments (`1005/subpart-A`, `1005/subpart-B`, `1006/subpart-A`,
  `1006/subpart-B`, `1006/subpart-D`). `uppercase_segments` moves 19,353 to
  19,358 in `schema/citation-path.v1.json`; every other family is unchanged and
  the result is OK.
- Re-fetch on 2026-10-20 (UTC; 2026-10-19 US Eastern): `full/2026-10-16/title-12.xml?part=1005` and `?part=1006`
  return bytes whose sha256 equals the retained files. A re-fetched
  `structure/2026-10-16/title-12.json` differs in bytes from the retained copy, but
  the part 1005 and 1006 subtrees and every other part node parse identical; the
  retained bytes are the ones the manifest hashes.
- `guard-ingested --base-ref origin/main --head-ref HEAD` with the repository's
  `AXIOM_CORPUS_INGEST_PUBLIC_KEY`: "All changed corpus artifacts have signed ingest
  manifests."
- R2: all 10 locked objects of the two scopes are present at their recorded sizes.
- `content-check` on both scopes: 0 findings.
- Independent review, round 1 (GPT-6.1 Sol, read-only): every one of the 42 section
  bodies matches the retained XML's paragraph text, markers included;
  structure-to-row comparison 30/30 and 19/19. Round 2 (Opus 5.5, read-only) checked
  the run-note corrections against the retained XML and structure JSON.

## Downstream

Staging, release cutting, activation and the rulespec-us re-pin are not part of
this change. The encoder resolves source text only from a verified signed
release, so the pilot encodes run after a release that carries these two scopes
is cut.
