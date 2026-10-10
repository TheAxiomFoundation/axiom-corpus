# California CalFresh BBCE authority

This source-first scope retains the minimum official California authority
hierarchy for CalFresh broad-based categorical eligibility, called modified
categorical eligibility (MCE) by California. It adds current Welfare and
Institutions Code §§18901.3 and 18901.5 and six CDSS All County Letters.

## Retained official sources

The source payloads were downloaded directly from the official California
Legislative Information and CDSS endpoints. They are retained byte-for-byte
without reserialization, OCR, or source-text correction.

| Source | Bytes | PDF pages | Rows | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| WIC §18901.3 HTML | 163,929 | — | 1 | `793afbd116aa7664fde4137f55d34ad659e80c10f37849d59bb4ea07b43fffdc` |
| WIC §18901.5 HTML | 164,166 | — | 1 | `97cae778729e0dd5d3c15797934690467876a14057e7d856d1500326e72d004e` |
| ACL 14-56 | 278,260 | 7 | 8 | `8677c1d3e5c2ec9ecef23206b24061999817a46fa469ccb68a000b8f2f570d5e` |
| ACL 14-56E | 189,729 | 4 | 5 | `67e33a2613009abaef3759ebc2a583417fb852120f009848e3b1a1e3c3c11cbd` |
| ACL 15-42 | 249,307 | 13 | 14 | `6aab92e4e2a2c9e0f234eba2b1c0eeb68d4d9d5dbc7ba752465a2358d9f2db33` |
| ACL 14-100 | 209,290 | 12 | 13 | `c981081163b361eea20aeeccec7934509dc5bf23d8d66c8035895586db60131e` |
| ACL 13-32 | 204,909 | 3 | 4 | `1a0bbfc2d6d69fd378aff3f1285d03d20b8b6abf2ff64c749b9897fd1cc55506` |
| ACL 14-63 | 120,344 | 2 | 3 | `4392ab0dedfcfb6f247bb7d3d913e90ff2a97a673ea01efac02ec9f3d6ee2841` |

All 41 PDF pages contain embedded text and each emits one page provision. The
six PDF document roots bring guidance coverage to 47/47 rows; WIC §§18901.3
and 18901.5 add two complete statute rows at
`us-ca/statute/wic/18901.3` and `us-ca/statute/wic/18901.5`. Because this is a
two-section slice, the rows' unresolved top-level parent links are cleared for
release self-containment; the official `us-ca/statute/wic` source hierarchy
remains recorded in metadata.

## Authority boundary

- WIC §18901.5 carries California's statutory categorical-eligibility mandate.
- WIC §18901.3 carries California's drug-felony opt-out and the
  probation/parole and fleeing-felon conditions for the covered cohort.
- ACL 14-56 carries the statewide PUB 275 trigger, inclusive 200 percent
  screen, and resource exclusion. Its zero-benefit discussion remains context.
- ACL 14-56E is the formal correction that CDSS requires readers to use with
  ACL 14-56.
- ACL 15-42 later restates the 200 percent boundary, MCE continuation/removal,
  and net-income treatment. Its examples are not an exhaustive current
  exclusions list.
- ACL 14-100 implements the removal of the former blanket prior-drug-felony
  exclusion effective April 1, 2015.
- ACL 13-32 carries the separate elderly/disabled route.
- ACL 14-63 is the focused authority for California's choice to deny or
  discontinue zero-benefit CE/MCE households of three or more; ACL 14-56 is
  retained as contextual implementation guidance.

### Current MCE-exclusions map

Current 7 CFR 273.2(j)(2)(vii) is retained in
`data/corpus/provisions/us/regulation/2026-07-15-title-7-part-273.jsonl` at
the exact row `us/regulation/7/273/2`. That federal row—not a California ACL—is
the controlling corpus authority for every federal gate below. The referenced
member-ineligibility provisions are retained in the same file at
`us/regulation/7/273/11`.

| Current federal gate | Exact controlling retained row | California overlay and current treatment |
| --- | --- | --- |
| Intentional program violation under §273.16 | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(A) | None; the federal gate applies. |
| Failure to comply with monthly reporting under §273.21 | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(A) | None; the federal gate applies. |
| Entire household is disqualified because one or more members failed to comply with workfare under §273.22 | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(B) | None; the federal gate applies. |
| Head of household fails work requirements under §273.7 | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(C) | None; the federal gate applies. |
| Member ineligible under the drug-felony rule in §273.11(m) | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(D) | WIC §18901.3(a), retained at `us-ca/statute/wic/18901.3`, opts California out for the described cohort; a qualifying conviction by itself is therefore not a current California exclusion. |
| Member is a fleeing felon or violates probation or parole under §273.11(n) | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(D) | WIC §18901.3(b), retained at `us-ca/statute/wic/18901.3`, confirms probation/parole compliance and fleeing-felon treatment for the subdivision (a) cohort; it does not replace the generally applicable federal gate. |
| Member is convicted of a serious crime and fails to comply with the sentence under §273.11(s) | `us/regulation/7/273/2`, paragraph (j)(2)(vii)(D) | None; both the serious-crime conviction and sentence-noncompliance conditions matter, and the federal gate applies. |

The distinct individual-member exclusions in 7 CFR
273.2(j)(2)(ix) are not collapsed into this household MCE-exclusions map.
Neither ACL 15-42's examples nor ACL 14-100's state-law implementation
instructions are represented as substitutes for the current federal text.

Historical dollar amounts and procedural workarounds in these letters are not
asserted as current figures. Current annual CalFresh amounts remain in the
separately retained ACIN I-46-25 scope.

## Deterministic offline reproduction

The 14 scoped artifacts—eight exact source snapshots plus inventory,
provisions, and coverage for the guidance and statute scopes—are reproduced by
this literal portable command:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py --base data/corpus
```

The script's `REPRO_COMMAND` constant is byte-for-byte identical to that
invocation. By default it reads the committed retained source paths. For a
bootstrap or CI lane supplied with the eight flat original files, it also
accepts a local source directory:

```bash
uv run --extra dev python scripts/repro/us_ca_calfresh_bbce_authority.py \
  --base data/corpus \
  --source-dir .ca-bbce-sources
```

Before writing output, the script hard-checks all eight hashes and sizes, all
six PDF page counts, and nonempty embedded text on every PDF page. It stages
both scopes, requires 47/47 and 2/2 coverage, verifies exact citation paths,
per-source row counts, retained-byte equality, official (non-`file://`)
metadata URLs, controlling authority excerpts, and the exhaustive per-gate
federal/state exclusions map.

The guidance manifest opts into source-specific text normalization that strips
exactly three known PDF accessibility strings whose presence varies by
PyMuPDF/MuPDF resolution. No shared extractor output changes unless a source
manifest opts in. Regeneration with the literal command above produces the
same committed bytes under both PyMuPDF 1.26.7 and 1.28.0.

No publication, R2 upload, Supabase load, release activation, RuleSpec
repository change, push, or GitHub mutation is part of this ingest. After the
round-two content commit landed, the main lane re-signed both ingest manifests
under `.axiom/ingest-manifests/` against the repaired artifacts: all applied
hashes match the committed files, each attested commit is an ancestor of the
signing commit, and `guard-ingested` passes. The superseded single-section
statute manifest, whose artifacts no longer exist under that version name, was
removed at the same time.
