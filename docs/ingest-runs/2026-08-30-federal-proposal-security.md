# Federal proposal-security authority corpus ingest

This scope supplies the primary federal and NSF sources needed for proposal-stage
security and submission checks. It deliberately excludes general award
administration, cost principles, post-award Part 170 reporting,
debarment/suspension, and the institution-of-higher-education-only authorities in
42 U.S.C. 19039-19040.

## Immutable federal sources

The US Code source is the OLRC release point `Online@119-102`, current through
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

The retained ZIP files each contain the byte-exact official XML member. The
113 MB Title 42 member exceeds GitHub's per-file limit, so it remains recoverable
from the retained 18 MB ZIP instead of being duplicated as a tracked uncompressed
file. The corpus adapter selected and verified the unmodified member directly
from each retained ZIP; no provision text was transcribed or reconstructed.

The eCFR source date is August 27, 2026, the newest version exposed by the eCFR
versioner API when this run was made. The August 28-30 structure endpoints returned
404.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Title 2 Part 25 XML | 18,189 | `6afb0be190a4b937ee1cffd49ffdff1289554225fb5c6acb26ba560cf8ffc52d` |
| Title 2 structure JSON | 1,349,222 | `8be0489b8a14aa1f821de4415caf8103f8bf943614bb473189094225a590be76` |
| Title 45 Part 604 XML | 36,211 | `c0adf8b08dff971b06984817826cbe7e94db190c9c36ae32724fee72c0ba2323` |
| Title 45 structure JSON | 4,107,005 | `aa178d9c9dc8410832f32d9b275f522ec28283b6af68f9d56b2b341f64ed4185` |

Part 604 Appendix B's official SF-LLL form is image-only. The adapter archived all
three Federal Register PNG renditions:

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

The supplement source HTML remains intact. Normalized effective-policy text drops
only HTML `s` elements that NSF explicitly marks as removed, retaining the added
replacement text. The TIP page is tagged as a dynamic external-list source; entity
names from its linked live lists must not be encoded into RuleSpec.

## Adapter commands and coverage

The statute adapters ran with repeated `--section` selectors and
`--include-title`:

```bash
uv run --extra dev axiom-corpus-ingest extract-usc \
  --base data/corpus --version 2026-08-30-proposal-security \
  --source-archive data/corpus/sources/us/statute/2026-08-30-proposal-security-title-31/olrc/xml_usc31@119-102.zip \
  --archive-member usc31.xml --title 31 \
  --source-as-of 2026-07-12 --expression-date 2026-07-12 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc31@119-102.zip \
  --section 1352 --include-title

uv run --extra dev axiom-corpus-ingest extract-usc \
  --base data/corpus --version 2026-08-30-proposal-security \
  --source-archive data/corpus/sources/us/statute/2026-08-30-proposal-security-title-42/olrc/xml_usc42@119-102.zip \
  --archive-member usc42.xml --title 42 \
  --source-as-of 2026-07-12 --expression-date 2026-07-12 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc42@119-102.zip \
  --section 1862o --section 6605 --section 19231 --section 19232 \
  --section 19233 --section 19234 --section 19235 --section 19237 \
  --include-title
```

The regulation and guidance adapters ran as follows:

```bash
uv run --extra dev axiom-corpus-ingest extract-ecfr \
  --base data/corpus --version 2026-08-30-proposal-security \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 2 --only-part 25 --workers 1

uv run --extra dev axiom-corpus-ingest extract-ecfr \
  --base data/corpus --version 2026-08-30-proposal-security \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 45 --only-part 604 --workers 1

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-08-30-federal-proposal-security-guidance \
  --manifest manifests/us-federal-proposal-security-2026.yaml
```

All five scopes completed with no missing or extra provisions:

| Scope | Matched provisions |
| --- | ---: |
| 31 U.S.C. 1352 plus title container | 73 |
| Selected Title 42 sections plus title container | 133 |
| 2 CFR Part 25, including Appendix A | 16 |
| 45 CFR Part 604, including Appendices A-B | 22 |
| Six NSF guidance documents and 19 scoped blocks | 25 |

The USLM and eCFR hierarchies add 110 genuine uppercase citation segments: 100
verbatim U.S. Code subsection letters and 10 eCFR subpart labels. The
`uppercase_segments` grammar ratchet is therefore raised from 7,007 to 7,117.
The single-block NSF TIP page uses the semantic leaf `implementation` rather
than introducing another synthetic `block-N` path.

No R2 synchronization, release publication, Supabase load, production activation,
or deployment was performed.
