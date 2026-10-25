# Montana separate-filing authority for tax years 2021-2023, and the pin cut that carries it

Date: 2026-10-25. Branch `ingest/us-mt-2021-2023-separate-filing-authority`, cut from #932's head
`bf1391948` (itself on `origin/main` 4d879d5b2).

- Scopes: `us-mt/regulation/2026-10-25-mt-separate-filing-dated-authority` and
  `us-mt/statute/2026-10-25-mt-separate-filing-dated-authority`.
- Manifests: `manifests/us-mt-separate-filing-dated-authority-regulation.yaml` and
  `manifests/us-mt-separate-filing-dated-authority-statute.yaml`.
- Selector: `manifests/releases/us-rulespec-2026-10-25-mt-separate-filing.json`, built by
  `scripts/repro/us_rulespec_2026_10_25_mt_separate_filing.py` and checked by
  `tests/test_us_rulespec_2026_10_25_mt_separate_filing.py`.

## Why

From tax year 2021 through 2023, Montana let married couples file jointly or separately: on the
same form (Filing Status 2a), on separate forms (2b), or with the spouse not filing (2c). From tax
year 2024 they must use their federal filing status (Form 2 instructions for 2023). rulespec-us's
household-choices register records
the choices this leaves to the couple: separate or joint filing, and how a couple filing
separately on the same form divides deductions and exemptions. rulespec-us#1844 left the Montana
entries out because the pinned release, `us-rulespec-2026-10-25-ssi-poms-public-laws`, carries
none of their texts:

| Text | Where it was |
| --- | --- |
| ARM 42.15.524 as in effect from 4/30/2010 | In no scope. The 42.15 scope taken from the current rules.mt.gov collection (`2026-09-14-income-tax-regulations-title-42-section-42-15`) has no subchapter 5 rules. |
| MCA 2021 15-30-2602 (Temporary), whose (2) gives the joint-return option | In no scope. The pin's `us-mt/statute/15-30-2602` (in `2026-07-16-pit-central-us-mt-title-15`) is the current text, which has no such option. |
| MCA 2021 15-30-2131, whose (1)(c)(vi) covers the dependent care deduction on the same form | `us-mt/statute/15-30-2131--mca-2021` in `us-mt/statute/2026-10-06-w6-income-tax-statute-mt-r2`, signed and locked on 2026-10-07 but not on the pin line. |
| Form 2 instructions for 2021, 2022 and 2023 | `us-mt/form/mtdor/ty202{1,2,3}/form-2-instructions` in `us-mt/form/2026-10-06-w6-income-tax-forms-mt`, signed and locked on 2026-10-07 but not on the pin line. |

This run ingests the first two and cuts a pin-line selector that adds all four scopes.

## ARM 42.15.524 (regulation scope)

**Source.** rules.mt.gov keeps every dated version of a rule in its policy library. Its public
API record of ARM 42.15.524 (collection `aec52c46-128e-4279-9068-8af5d5432d74`, policy
`1223c9d6-74a1-4199-83e9-1f46a6cc8993`) marks the rule INEFFECTIVE and lists its versions:

| Version | Start | End | Accessible HTML (SHA-256) |
| --- | --- | --- | --- |
| 30622 (`908d23f8-9eb7-473d-b812-9cffe9caa986`) | 2010-04-30 | 2025-01-24 | `9064d3790b481f208c10c7a2cb985a4b75f44dbcc8b5342afc52471ac6232074` |
| REP 42-1088 (`011eb6b8-6f8c-41fc-b03c-50c156cd5267`) | 2025-01-25 | none | the repeal notice |

The repeal version's history ends "REP, 2025 MAR, Notice No. 42-1088, Eff. 1/25/25". Version
30622 therefore covers tax years 2021 through 2023. Its API document URL (version document
`46345c20-386c-420b-8b13-d273c1320d38`) redirects to
`https://rules.mt.gov/policy-library-documents/text/html/9064d379…`, whose last segment is the
document's SHA-256 as the record's `contentHashSha256` gives it. That URL is `download_url`.
Fetched on 2026-10-25, it returned 7,282 bytes with that SHA-256, and the extractor stored the
same bytes. `source_url` is the rule's browse page on rules.mt.gov.

**Why no scope had it.** The 42.15 scope (`2026-09-14-income-tax-regulations-title-42-section-42-15`)
was taken with the Montana rules extractor, which keeps only a section's child policies whose
`effectiveStatus` is `EFFECTIVE` unless it is told to include the others. The repealed 42.15.524
is INEFFECTIVE, so that scope has no subchapter 5 rules.

**Corroboration.** The rule's former gateway page,
`https://rules.mt.gov/gateway/ruleno.asp?RN=42.15.524` (earlier `mtrules.org`), now redirects
to the rules.mt.gov search application. The Internet Archive's status-200 captures of it from
20171002103641 on have two payload digests: `WU5PTJCQQMBR2FZXM6MONOFMAYJ7WUP6` (mtrules.org,
20171002103641, 20191206060408 and 20201030190413) and `76DU6CPDVYM7ZVKJMKACM5EESQ2OATLX`
(rules.mt.gov, 20220701053000 to 20240611163609). Earlier captures have other digests. The
20231003110140 capture (14,442 bytes, SHA-256
`d856d16f35e6737df9cac3155bcc58aaf9c52d7be78c8a38fd220f2bef449411`) carries the same words in
(1) through (5) as version 30622 and a history ending with the 2010 amendment. The manifest
records it under `archive_corroboration_*`; the corpus does not store it.

**Rows.** `html_content_selector: '#documentBody'` keeps the rule, its authorizing and
implementing statutes and its history. Two rows:

- `us-mt/regulation/title-42/chapter-42-15/subchapter-42-15-5/rule-42-15-524--effective-2010-04-30`:
  the document row, no body.
- `…/block-1`: the rule, (1) through (5), the statutes and the history.

**Path.** schema/citation-path.v1.md section 4.0: a version other than the one at a section's plain
path is a sibling `<section>--<slug>` with `metadata.variant` and `metadata.canonical_citation_path`.
Montana's MCA editions already use this path form (`15-30-2131--mca-2021`, whose plain path
holds the repealed section), though that row carries no variant metadata. The plain path stays free for the rule's current page. The subchapter segment
follows the 42.15 scope (`subchapter-42-15-1` for 42.15.1xx).

**Citation-path ratchet.** The extractor carries each unsegmented page in one `block-1` leaf, as it
did for `15-30-2131--mca-2021/block-1`. The two leaves add 2 paths to the `block_n` irregular
family, which `scripts/validate_citation_paths.py` caps. `schema/citation-path.v1.json` raises
that baseline from 105417 to 105419 and records why; the CI scan of the merged tree measured
105419. Segmenting by subsection instead would collide on the MCA page, which prints (1) through
(5) twice (the temporary text and the text effective January 1, 2024).

**Dates.** `expression_date` and `metadata.effective_start` are 2010-04-30 and
`metadata.effective_end` is 2025-01-24, version 30622's start and end dates. `source_as_of` is
2026-10-25, the retrieval date. `metadata.repeal_note` records the repeal, and the policy,
version and document ids are in `metadata`.

## MCA 2021 15-30-2602 (statute scope)

**Source.** The Legislature still serves the Montana Code Annotated 2021 edition at
`https://mca.legmt.gov/bills/2022/mca/...`, the source family the w6 scope used for
`15-30-2131--mca-2021`. The 15-30-2602 page answered HTTP 200 on 2026-10-25. Its header reads
"Montana Code Annotated 2021", and it prints the temporary text and the text effective January 1,
2024. The temporary (2) reads, in part, "may, at the taxpayer's option, file a joint return".
The 2023 edition (`/bills/2023/mca/...`, fetched the same day) prints only the text effective
January 1, 2024, with its history ending "amd. Sec. 7, Ch. 563, L. 2023", so it is no source for
tax year 2023. That year rests on the 2021 edition's temporary text, which held until the later
text took effect on January 1, 2024, and on the 2023 Form 2 instructions, which still give
couples the choice of filing jointly or separately.

**Rows.** `html_content_selector: body`, as for `15-30-2131--mca-2021`. Two rows:
`us-mt/statute/15-30-2602--mca-2021` (document, no body) and `…/block-1` (6,040 characters, both
texts and the history). `metadata.variant` is `mca-2021` and `metadata.canonical_citation_path` is
`us-mt/statute/15-30-2602`.

**Dates.** The page has no date of its own. `expression_date` and `source_as_of` are 2026-10-25, the
retrieval date, as the w6 scope did for `15-30-2131--mca-2021`. `metadata.code_edition` and
`metadata.expression_date_note` say so.

## Signing and objects

Both scopes have 2 inventory items and 2 provisions, with coverage complete (0 missing, 0 extra), and
`content-check` reports no findings. Each signed manifest names the manifest commit `114ba7752` with
`dirty_tracked: false`. `corpus push` uploaded the 8 new objects (60,835 bytes); a dry run afterwards
reports all 8 in R2. No release was published or activated, and nothing was loaded into Supabase.

## Selector

`us-rulespec-2026-10-25-mt-separate-filing` = #932's `us-rulespec-2026-10-25-nyc-ch127-title-52`
(272 scopes) plus:

- `us-mt/form/2026-10-06-w6-income-tax-forms-mt`;
- `us-mt/regulation/2026-10-25-mt-separate-filing-dated-authority`;
- `us-mt/statute/2026-10-06-w6-income-tax-statute-mt-r2`;
- `us-mt/statute/2026-10-25-mt-separate-filing-dated-authority`.

That makes 276 scopes. None of the four is withdrawn. The base selected no `us-mt/form` scope. The
added rows' 38 citation paths are distinct and meet none of the 2,395 paths of the us-mt statute and
regulation scopes the base selects. The w6 statute scope also brings the MCA 2019 text of 15-30-2131,
2021 SB 399 (enrolled and version 3) and 2023 HB 192 and HB 222, and the forms scope brings Form 2 for
2021-2024, the 2024 instructions (and their 2024-12-03 revision), Schedule 2EC for 2024 and Form
2441-M for 2022. No rulespec-us module on `main` cites any of these paths, so adding them moves no
module's validation.

It keeps the base's three withdrawn scopes, `us-me`, `us-mi` and `us-mn` `statute/2026-07-13-recovery`.
Allowances do not carry forward, so `manifests/withdrawn-scopes.yaml` records an exception for this
selector on each, pinned to its digest (`642d9a8d…`), with the same reason as #932's.

## Checks

`tests/test_us_rulespec_2026_10_25_mt_separate_filing.py` (16 tests):

- the reproducer's output is byte-identical to the committed selector;
- the delta against the base is the four scopes, given as literals in the test;
- each added scope is locked and not withdrawn, and the selector adds no withdrawn scope;
- each kept withdrawn scope has its own exception, and the quality profile is unchanged;
- the selected us-mt scopes share no citation path (`duplicate_release_citation`);
- both dated rows sit at `<plain path>--<variant>` with matching variant metadata;
- the ARM source file's SHA-256 is the archive payload SHA-256, and its dates are as above;
- the dated rows hold the texts rulespec-us will cite;
- a Hypothesis property of the build rule: for any duplicate-free base without an addition, the
  output is the base plus the additions, sorted, with nothing dropped; any other base is refused
  with "already selects".

Mutation checks, each run under an RSS cap of 2 GB: dropping the dated statute scope from the selector
fails 4 tests; removing the "already selects" refusal fails the property; a row at an
already-selected path in the dated statute scope fails 2 tests; sorting the selector by version only
fails 2 tests.

`scripts/publish_corpus.py --release us-rulespec-2026-10-25-mt-separate-filing --dry-run` ran on a
fully fetched tree; its result is recorded in the pull request.

## Release line

#932 cuts `us-rulespec-2026-10-25-nyc-ch127-title-52`, and this selector is built on it, so it carries
#932's NYC Administrative Code swap and Title 52 scope as well. Merge #932 first. If both merge before
#932's release is published, publishing only this release would save rulespec-us one re-pin; either
way the re-pin that takes this release brings #932's NYC validation changes with it unless
rulespec-us has already taken #932's. #926 (Kansas LIHEAP) is still cut on an older pin and must be
rebuilt on the last pin-line selector to merge, as #932's run note describes.

## After merge

1. Dispatch `publish.yml` with this release, then `mirror-release.yml`. **Publish only. Do not
   activate it.** It is a pin release for rulespec-us; see `docs/named-release-publication.md`.
2. Re-pin rulespec-us to this release with the published `content_sha256`, then add the Montana
   household-choices entries that cite these paths.

## Commands

```bash
axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-10-25-mt-separate-filing-dated-authority --manifest manifests/us-mt-separate-filing-dated-authority-regulation.yaml
axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-10-25-mt-separate-filing-dated-authority --manifest manifests/us-mt-separate-filing-dated-authority-statute.yaml
axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus --jurisdiction us-mt --document-class <regulation|statute> --version 2026-10-25-mt-separate-filing-dated-authority --command '<the extract command>' --lock
axiom-corpus-ingest content-check us-mt/<regulation|statute>/2026-10-25-mt-separate-filing-dated-authority
axiom-corpus-ingest corpus push us-mt/regulation/2026-10-25-mt-separate-filing-dated-authority us-mt/statute/2026-10-25-mt-separate-filing-dated-authority
python scripts/repro/us_rulespec_2026_10_25_mt_separate_filing.py
```

The CDX index was queried at `https://web.archive.org/cdx/search/cdx`. Captures were fetched with
`curl` from the `id_` URLs. Digests were computed with `shasum -a 256`, and SHA-1 base32 with Python's
`hashlib` and `base64`.
