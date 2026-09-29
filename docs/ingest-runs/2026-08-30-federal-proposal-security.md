# Federal proposal-security authority corpus ingest

This pack holds the federal and NSF sources selected for the initial proposal-stage
security and submission RuleSpec spine: the lobbying certification and disclosure
rule (31 U.S.C. 1352, 45 CFR Part 604), UEI/SAM registration (2 CFR Part 25), the
CHIPS and Science Act research-security provisions and their definitions, and NSF's
proposal-stage implementation guidance. It deliberately excludes general award
administration, cost principles, post-award Part 170 reporting, debarment/suspension,
and the institution-of-higher-education-only authorities in 42 U.S.C. 19039-19040.
PAPPG 24-1 Chapters II-III, NSF 26-506 (PESOSE) and the 2 CFR Part 200 slice are held
by `us/guidance/2026-09-24-nsf-pappg-pesose` and
`us/regulation/2026-09-24-nsf-slice-title-2-part-200` (axiom-corpus#631), not here.
"Unselected neighbouring sources" below lists what was left out and why.

The pack was first built on 2026-08-30 on top of the unmerged axiom-corpus#635, and
rebuilt on `main` on 2026-09-28/29 with main's adapters (axiom-corpus#636). The U.S.
Code scopes were re-extracted from the same retained release-point zips with
`extract-usc --source-zip` and made self-contained. The eCFR scopes were regenerated
byte-identical. The NSF pages were re-captured on 2026-09-28 (see "Regeneration on
main").

| Scope | Rows |
| --- | ---: |
| `us/statute/2026-08-30-proposal-security-title-31` (31 U.S.C. 1352) | 72 |
| `us/statute/2026-08-30-proposal-security-title-42` (42 U.S.C. 1862o, 1862o–1, 6605, 18901, 19036, 19231-19237) | 174 |
| `us/regulation/2026-08-30-proposal-security-title-2-part-25` (2 CFR Part 25, including Appendix A) | 16 |
| `us/regulation/2026-08-30-proposal-security-title-45-part-604` (45 CFR Part 604, including Appendices A-B) | 22 |
| `us/guidance/2026-09-28-federal-proposal-security-guidance` (six NSF documents, 19 scoped blocks) | 25 |

Every scope has complete coverage: source rows equal provision rows, with 0 missing and
0 extra. Every parent link resolves inside the scope, and each scope carries a signed
ingest manifest under `.axiom/ingest-manifests/us/<class>/<version>.json`.

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

Both zips were downloaded again from these URLs at 2026-09-29T02:49Z, and both are
byte-identical to the retained files. Each scope retains its zip byte-for-byte under
`sources/us/statute/<scope>/olrc/` as its only source file. Every inventory item and
provision row has a `source_path` pointing at the zip. Every inventory `sha256` equals
the zip's hash, and `metadata.source_archive_member` names the member that was parsed
in memory. This is the `extract-usc --source-zip` convention of
`docs/ingest-runs/2026-09-13-federal-statute-layer.md`. The 113 MB Title 42 member
exceeds GitHub's 100 MB per-file limit, so it is recovered from the retained 18 MB zip
rather than tracked uncompressed.

The eCFR source date is August 27, 2026. The 2026-08-30 capture recorded this as the
newest version the eCFR versioner API exposed at the time.

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Title 2 Part 25 XML | 18,189 | `6afb0be190a4b937ee1cffd49ffdff1289554225fb5c6acb26ba560cf8ffc52d` |
| Title 2 structure JSON | 1,349,222 | `8be0489b8a14aa1f821de4415caf8103f8bf943614bb473189094225a590be76` |
| Title 45 Part 604 XML | 36,211 | `c0adf8b08dff971b06984817826cbe7e94db190c9c36ae32724fee72c0ba2323` |
| Title 45 structure JSON | 4,107,005 | `aa178d9c9dc8410832f32d9b275f522ec28283b6af68f9d56b2b341f64ed4185` |

Part 604 Appendix B, the SF-LLL form, is image-only in the official source. The adapter
archived all three Federal Register PNG renditions, and the body of the `appendix-b`
row references each one:

| Graphic | Bytes | SHA-256 |
| --- | ---: | --- |
| `EC01JA91.007.png` | 4,121 | `8fe4e55182918231b96bb881d20dc5ccfb97865b2037a2fe3a6cfdd68cf050ff` |
| `EC01JA91.008.png` | 8,087 | `03394bcac854e8e8a7de7124d10faafbc04e2ef80a02760d06300305742e1ec1` |
| `EC01JA91.009.png` | 688 | `cf1ebd4003cd8e54e4e6e252fb06e7062d096bca62f50b780f3fb74ec06a107c` |

## U.S. Code sections

Title 31: section 1352 (limitation on use of appropriated funds to influence certain
Federal contracting and financial transactions).

Title 42:

| Section | Heading | Rows | Why |
| --- | --- | ---: | --- |
| 1862o | Postdoctoral research fellows | 3 | proposal mentoring-plan requirement |
| 1862o–1 | Responsible conduct of research | 4 | requires each applying institution to describe, in its grant proposal, a plan for training that includes research-security threat awareness (amended by CHIPS §10337) |
| 6605 | Disclosure of funding sources in applications for Federal research and development awards | 39 | application disclosure |
| 18901 | Definitions | 36 | defines "Federal research agency", "research and development award" and other terms used throughout 19231-19237, which does not define them itself |
| 19036 | Authorities | 1 | NSF's authority to run risk assessments of award applications and disclosures, the basis of Important Notice 149 item 1 |
| 19231-19237 | Part C, Research Security (all seven sections) | 91 | foreign talent recruitment programs, the malign-program prohibition, contract review, training, the person-or-entity-of-concern prohibition, nondiscrimination, definitions |

Part C's rows break down as follows: 19231 10, 19232 13, 19233 12, 19234 18, 19235 4,
19236 1, 19237 33. Section 1862o–1 is spelled with the USLM en dash (U+2013), as the
other held dashed sections are (for example `us/statute/42/1396u–1`). `--section`
accepts only ASCII section numbers, so it is selected with `--citation-path`.

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

| Captured page (2026-09-29T03:43Z) | Bytes | SHA-256 |
| --- | ---: | --- |
| `nsf-pappg-24-1-chapter-i-submission-security.html` | 108,415 | `9d1657a1aff7badcd7098e1010aac6826fb177df322790c703efae9f8363c3d9` |
| `nsf-pappg-24-1-supplement-1-proposal-security.html` | 86,266 | `9467cd79bcf409b7491d54f6b5b8c7c850069b91ded6e3f00cc70d287ab4c6ae` |
| `nsf-pappg-24-1-supplement-2-dmsp.html` | 73,976 | `28f5d87f3b836b6317ea5bb5aeac29cc14bc6e5470f2eefeb692b67d988b44fd` |
| `nsf-important-notice-149-proposal-security.html` | 78,629 | `ae878b521bb0a105ea51260f7ef33c3e2a314c84bf12e042d465daeacdb45193` |
| `nsf-important-notice-149-implementation-faq.html` | 69,138 | `0d676fb0fd02ef5b56ed08c79b08636afa21bddb3441a71e3c8a134e539febc3` |
| `nsf-tip-person-entity-of-concern-prohibition.html` | 54,913 | `ed3c4dfdccb07d1022f22d574738917e733e117c45136329d9c162231c268b81` |

The supplement source HTML is retained intact. The supplements mark revisions inline:
underlined text is added and struck text is removed. The normalized effective-policy
text drops the struck HTML `s` elements and keeps the underlined replacement text. The
extraction also drops the page's `.print` chrome; on Chapter I it drops the accordion
and sidebar as well.

The Supplement 2 page puts its page-level "Contact information" h2 and two paragraphs
inside the same layout block as section 3. A block range therefore cannot stop before
them, so two drop selectors remove them. The paragraphs are dropped first, because once
the h2 is gone, `h2 ~ p` matches nothing.

The TIP page is tagged `dynamic_external_lists` and
`prohibited_entity_names_must_not_be_encoded`. Entity names from its linked live lists
must not be encoded into RuleSpec. The single-block TIP page uses the semantic leaf
`implementation` rather than a synthetic `block-N` path. Its `expression_date` is the
capture date, because the page is a living implementation page. The list versions it
cites are Federal Register documents 2026-11571 (June 10, 2026, current), 2025-00070,
2024-06895, 2021-13753 and 2021-13755. Their URLs are in the retained HTML, not in the
row body. The other five documents use their publication or effective dates.

Placement notes for encoders:

- The FAQ page nests its "Footnotes" heading and footnotes 1-7 inside the question 9
  answer, so the `question-9` row ends with them. Their markers belong to questions 1
  (footnotes 1-6) and 5 (footnote 7).
- Important Notice 149 items 2 and 4 carry footnote markers 1 and 2. The footnote text
  sits in the page's second main layout region, which the content selector does not
  read. Both notes are forward-looking: NSF intends to develop foreign-travel security
  training, and to expand the annual MFTRP certification to all senior/key personnel.

## Adapter commands

`extract-usc` appends `-title-<n>` to `--version` (`usc_run_id`). `extract-ecfr`
appends `-title-<n>-part-<p>`. The U.S. Code commands expect the two release-point
zips in the working directory; download them from the URLs above or point
`--source-zip` at the retained copies. The adapter names the retained file after the
input file, so keep the publisher's file name.

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
  --section 1862o --citation-path 'us/statute/42/1862o–1' --section 6605 \
  --section 18901 --section 19036 --section 19231 --section 19232 --section 19233 \
  --section 19234 --section 19235 --section 19236 --section 19237

uv run python scripts/self_contain_usc_scope.py --base $B \
  --version $V-title-31 --version $V-title-42

uv run axiom-corpus-ingest extract-ecfr --base $B --version $V \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 2 --only-part 25 --include-appendices --workers 1

uv run axiom-corpus-ingest extract-ecfr --base $B --version $V \
  --as-of 2026-08-27 --expression-date 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices --workers 1

uv run axiom-corpus-ingest extract-official-documents --base $B \
  --version 2026-09-28-federal-proposal-security-guidance \
  --manifest manifests/us-federal-proposal-security-2026.yaml
```

Run live, the NSF command re-fetches the pages, and their bytes change with page chrome.
To reproduce the retained artifacts, replay the manifest with each document's
`local_path` set to its capture. A local replay records `metadata.download_url` as a
`file://` path and `metadata.content_type` as null; everything else matches (see
`test_guidance_scope_replays_from_the_retained_captures`).

`--source-as-of`/`--expression-date` 2026-07-12 is the release point's currency date,
the convention of the other retained-zip U.S. Code scopes. Each member's XML creation
date is in every row's `metadata.created_date`: 2026-05-04 for Title 31 and 2026-07-23
for Title 42.

## Self-containment

`us/statute/42` is already carried by the released
`us/statute/2026-07-19-rulespec-title-42-consolidated`. A release selector with the
`complete-expression-dates-v1` quality profile, as the US union selectors have, cannot
carry a citation path twice (`duplicate_release_citation` is an error). The 2026-08-30
build included the title rows (`--include-title`), so its Title 42 scope collided with
the `us-rulespec-2026-09-14-wave4-r2-union` selection on `us/statute/42`.

The rebuild follows `docs/ingest-runs/2026-09-13-federal-statute-layer.md` instead. It
carries no title row, and `scripts/self_contain_usc_scope.py` detaches each section
row's out-of-scope parent: it clears `parent_citation_path`/`parent_id`, sets
`metadata.self_contained_root: true`, and records
`metadata.detached_parent_citation_path: us/statute/<title>`. No scope carries
`us/statute/31`. Title 31 takes the same shape, so a later Title 31 scope can carry the
title row without a collision. There are 1 detached root in Title 31 and 12 in Title
42, one per section.

## Regeneration on main

- **U.S. Code.** The nine sections of the 2026-08-30 build came out with the same
  citation paths (less the two title rows) and identical headings and bodies. Only
  provenance fields changed. Main's adapter records `source_format: uslm-xml` and
  `metadata.source_archive_member`, where #635's unmerged adapter recorded
  `uslm-xml+zip`, `archive_member`, `archive_member_sha256` and `archive_sha256`. The
  section rows are now detached roots. Sections 1862o–1, 18901, 19036 and 19236 were
  added on 2026-09-29 after the verification described below.
- **eCFR.** Re-running both `extract-ecfr` commands above live on 2026-09-29 produced
  source, inventory, provisions and coverage files byte-identical to the 2026-08-30
  artifacts. Main needs `--include-appendices` for the appendix rows (axiom-corpus#634).
- **NSF.**
  - Main's extractor, replayed offline over the six 2026-08-30 captures, reproduced the
    2026-08-30 artifacts, apart from the two replay-only fields.
  - Verification then found that the section 3 row of Supplement 2 also carried the
    page's "Contact information" section. The drop selectors above fix that.
  - A local replay cannot record the live `download_url` and `content_type`, so the
    pages were re-captured live at 2026-09-29T03:43Z (`source_as_of` 2026-09-28, local
    date) into `us/guidance/2026-09-28-federal-proposal-security-guidance`. That version
    replaces `2026-08-30-federal-proposal-security-guidance`.
  - Against the 2026-08-30 rows, the only differences are the removed "Contact
    information" text and the TIP page's capture date.

## Currency checks (2026-09-29)

- **U.S. Code.** The current release point is Public Law 119-111 (09/18/2026), per
  `https://uscode.house.gov/download/download.shtml`. The same selectors were extracted
  from `xml_usc31@119-111.zip` (SHA-256
  `c49c36893cc350fea84d458645c95e6883fe8c7b927976913e86b452e6a5df4d`) and
  `xml_usc42@119-111.zip` (SHA-256
  `d2df95e45d3bc365a4bfcbeb346e6a828abd7f41bfd8915be3600112a29d7a01`). They give the
  same 72 and 174 citation paths, with identical headings, bodies, kinds and parents, so
  the 119-102 text is also the current text. Rows keep the default prelim reader
  `source_url`, and `--prior-release-point` is not needed.
- **eCFR.** The versioner API reports the latest amendment of 2 CFR Part 25 as
  2024-10-01 and of 45 CFR Part 604 as 2016-09-12. Both titles are up to date as of
  2026-09-25, so the 2026-08-27 text is current.
- **NSF.** The captures are from 2026-09-29.

## Unselected neighbouring sources

| Source | Why it is not in this pack |
| --- | --- |
| 42 U.S.C. 1862o–2, 1862o–3 | reporting and sharing of research results. 1862o–3's future-award ineligibility follows post-award noncompliance and is not a security check. |
| 42 U.S.C. 1862o–15 | directs NSF to allow a full proposal after each meritorious preproposal; an agency process rule, not an applicant security condition |
| 42 U.S.C. 18912 | Department of Energy research security (subchapter I), not NSF or government-wide |
| 42 U.S.C. 19031-19035, 19037, 19038 | NSF Part D organization, reporting, online resources, research awards, the information-sharing organization, and the controlled-information plan; agency-internal |
| 42 U.S.C. 19039-19040 | institution-of-higher-education-only (Confucius Institutes; annual foreign financial support disclosure) |
| PAPPG 24-1 Ch. I outside G.1-G.2 (for example I.E.3(b), I.F, I.G.3-G.4), Supplement 1 outside sections 5 and 12, Ch. IV.B | not extracted in this pack; a follow-up can extend the manifest's anchor ranges |
| 2 CFR 200.206 | agency pre-award risk review; held by neither this pack nor the Part 200 slice |

## External dependencies

The selected sections rely on authorities this pack does not hold. Treat them as
parameters or external lists:

- The 19235 prohibition uses the lists under section 1237(b) of the NDAA for FY1999
  (50 U.S.C. 1701 note) and section 1260H of the NDAA for FY2021 (10 U.S.C. 113 note).
- 19232 relies on the lists under section 1286(c)(8)-(9) of the NDAA for FY2019
  (10 U.S.C. 4001 note).
- 6605 cites NDAA for FY2020 section 1746(a).
- 19237 cites 8 U.S.C. 1189(a), 10 U.S.C. 4872 and 50 U.S.C. 4801 et seq.

The live entity lists behind these are dynamic. The TIP page flags them as such.

## Known text-joiner artifacts (main's adapters)

These come from main's adapters and are left as is here:

- `extract-usc` inlines OLRC footnotes mid-sentence. For example, 42 U.S.C.
  6605(c)(4) reads "to contest 2 2 So in original. ...". This affects 17 rows in
  sections 1352, 6605, 19231, 19232, 19235 and 19237, the footnoted provisions and
  their ancestors. Main's other U.S. Code scopes behave the same way.
- `extract-usc` and the HTML extractor insert a space around inline elements, as in
  "title 5 , and" or "Research .gov".

Fixing either changes bytes across many signed scopes, so each is tracked as a separate
adapter task.

## Citation-path grammar

The five scopes add 115 unique paths with an uppercase character: 105 U.S. Code paths
and 10 eCFR subpart labels (`us/regulation/2/25/subpart-A` to `subpart-D`,
`us/regulation/45/604/subpart-A` to `subpart-F`). The U.S. Code paths are 68
subparagraph rows plus 37 clause rows beneath them. The four `1862o–1` rows add four
en-dash paths.

In `schema/citation-path.v1.json`, `uppercase_segments` is raised from main's 16,281 to
16,396 and `endash_segments` from 1,652 to 1,656. `scripts/validate_citation_paths.py`
then passes. Other branches that raise these ceilings will conflict on those lines;
recompute them on merge.

## Release validation

| Selector (scratch, not tracked) | Scopes | Result |
| --- | ---: | --- |
| the five scopes, `--strict-warnings` | 5 | `ok: true`, 0 errors, 0 warnings |
| `us-rulespec-2026-09-14-wave4-r2-union` plus the five scopes, `--ignore-r2-missing` | 1,047 | `ok: true`, 0 errors, 546 warnings, none naming these scopes |

The 546 warnings are the pre-existing 541 `missing_parent_id` and 5
`unsectioned_document_body` recorded in
`docs/ingest-runs/2026-09-23-tax-statute-policybench.md`. None of the 309 citation
paths is carried by any tracked `us` provisions file outside this pack.

## Signing

The artifacts were force-added (`data/` is gitignored) and committed. Each scope was
then signed against a clean commit with `axiom-corpus-ingest sign-ingest-manifest`,
recording the rebuild command above. Title 31 and the two eCFR scopes were signed at
the first artifact commit. Title 42 and the guidance scope were re-signed after the
2026-09-29 changes.

`tests/test_federal_proposal_security_manifest.py` checks the following:

- Each manifest attests exactly its scope's artifacts at their committed SHA-256.
- The signatures verify under `AXIOM_CORPUS_INGEST_PUBLIC_KEY`. The test is skipped
  locally without the key and fails in CI.
- The Title 31 scope rebuilds byte-identically from the retained zip. The Title 42
  rebuild is marked `slow`.
- The guidance scope replays from the retained captures.

No R2 synchronization, release selector, publication, Supabase load, production
activation, or deployment was performed.
