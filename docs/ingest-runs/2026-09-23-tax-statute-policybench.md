# Title 26 sections for the PolicyBench oracle encodings (2026-09-23)

PolicyBench found engine defects in policyengine-us whose governing federal law was missing from the
corpus or not resolvable at the needed citation. This run adds two `us/statute` scopes from the
official U.S. Code (Office of the Law Revision Counsel, uscode.house.gov, USLM XML) with the
`extract-usc --source-zip` adapter and `scripts/self_contain_usc_scope.py`, the same path as the
2026-09-13 federal statute layer (`docs/ingest-runs/2026-09-13-federal-statute-layer.md`).

| Scope (`us/statute`) | Sections | Rows | Source | Expression date | Root causes |
| --- | --- | ---: | --- | --- | --- |
| `2026-09-23-tax-statute-policybench-title-26` | 402A, 662, 852 | 298 | release point 119-103 | 2026-09-02 | r08 (402A), r03 (662), r32 (852) |
| `2026-09-23-tax-statute-policybench-rp-118-209-title-26` | 67, 170 | 506 | prior release point 118-209 (except 118-159) | 2024-12-23 | r11 (2024 vintage) |

Both scopes: coverage complete (source rows = provision rows, 0 missing, 0 extra, 0 duplicate
citations), every row has a heading or a body, section rows are self-contained roots
(`metadata.detached_parent_citation_path: us/statute/26`). Each scope's four artifact kinds still
have to be force-added and attested by a signed ingest manifest when this run is committed (see
"Not done").

## Sources

| Release point | Zip URL | Zip bytes | Zip SHA-256 | Member | Member bytes | Member SHA-256 | Retrieved |
| --- | --- | ---: | --- | --- | ---: | --- | --- |
| 119-103 (09/02/2026) | `https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc26@119-103.zip` | 8,290,374 | `285b9862808f26055c3eed16c2aca1d8de1fae96b581f44a55cfedb907a46eff` | `usc26.xml` | 55,871,474 | `ab999da948658a2265f762abfedd72413a3f7828d34659ff27ed8240fcd956e4` | retained by the 2026-09-13 closure scope; re-downloaded 2026-09-23T16:00:10Z, identical bytes |
| 118-209 except 118-159 (12/23/2024) | `https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/xml_usc26@118-209not159.zip` | 8,162,829 | `92e448a694abbf65e8c7272ec88be3bf9e57818cb3d1cc7bc2624b937cb83148` | `usc26.xml` | 55,002,607 | `d8c9b276af1ffec7da5ba416be8888726d44b6e0de2a2df4f5a2b6fd0d720bec` | 2026-09-23T15:55:09Z |

The 119-103 zip was taken from
`data/corpus/sources/us/statute/2026-09-13-tax-statute-closure-31-title-26/olrc/`, and each scope
retains its zip byte-for-byte under `sources/us/statute/<scope>/olrc/` as its only source file. The
118-209 member carries `docPublicationName Online@118-209not159` and `dcterms:created
2025-01-14T03:14:56`.

Checked but not retained (comparison only):

| Source | URL | SHA-256 | Retrieved |
| --- | --- | --- | --- |
| OLRC 118-274 except 118-159 (01/06/2025) | `https://uscode.house.gov/download/releasepoints/us/pl/118/274not159/xml_usc26@118-274not159.zip` | `a5336c3a3e4d2f55ccd0c3027e56912966f7adb181d110012110d64816c324ce` | 2026-09-23T15:55:09Z |
| OLRC 119-110 (09/16/2026, current per `download.shtml` on 2026-09-23) | `https://uscode.house.gov/download/releasepoints/us/pl/119/110/xml_usc26@119-110.zip` | `afd6c5e19dc9ef79bb4e8f359c5059138fc51a758c5c34bb80b7ad96638363f0` | 2026-09-23 |
| GovInfo USCODE-2024 sec. 67 | `https://www.govinfo.gov/content/pkg/USCODE-2024-title26/html/USCODE-2024-title26-subtitleA-chap1-subchapB-partI-sec67.htm` | `5ffe55c0947750ae010fb4163e349d788e65aa4597992ec690e05b10e9a68e1f` | 2026-09-23T15:55:15Z |
| GovInfo USCODE-2024 sec. 170 | `https://www.govinfo.gov/content/pkg/USCODE-2024-title26/html/USCODE-2024-title26-subtitleA-chap1-subchapB-partVI-sec170.htm` | `53cab7897a101352b6d7ab08084f16b85a76c61c18fd003ce34fc31124524de2` | 2026-09-23T15:55:15Z |

## 402A, 662 and 852 (current text)

Whole sections from release point 119-103, the zip the 2026-09-13 closure scope already retains. Rows:
402A 131 (6 subsections, 30 paragraphs, 50 subparagraphs, 40 clauses, 4 subclauses), 662 8
(subsections (a)-(c), (a)(1)-(2), (a)(2)(A)-(B)), 852 159 (7 subsections, 26 paragraphs, 55
subparagraphs, 49 clauses, 21 subclauses), including 852(b)(3)(A)-(E) and (b)(3)(C)(i)-(vi).
`us/statute/26/852/b/3/C/vi` has a heading and an empty body because the source clause is
`<content/>`; the following `<continuation>` ("For special rule for certain losses after October 31,
see paragraph (8).") is in the body of `us/statute/26/852/b/3/C`.

Currency: the current release point is 119-110 (09/16/2026), and 119-108 (09/11/2026) affected Title
26. Extracting the same three sections from the 119-110 zip gives the same 298 citation paths with
identical headings and bodies, so the 119-103 text is also the current text.

None of the 298 citation paths is carried by any `us/statute` provisions file in the repository.

## 67 and 170 (2024 vintage)

The current text of 67 and 170 is held by
`us/statute/2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup` (release point 119-100,
expression date 2026-07-13, post-OBBBA). This scope is a distinct vintage under the same citation
paths; nothing in the recovery scope was touched.

Release point choice: the OLRC prior release points page lists 118-209 (12/23/2024) followed by
118-233 (01/04/2025), so 118-209 is the last release point dated before January 1, 2025. Evidence
that its text of 67 and 170 is the text in force on that date:

- The 118-209 and 118-274 (01/06/2025) extractions of 67 and 170 have the same 506 citation paths
  with identical headings and bodies, so no law enacted between the two release points changed
  either section.
- Word-level comparison against the GovInfo USCODE-2024 HTML (the 2024 main edition,
  `currentthrough:20250106`, which unlike the two release points also incorporates Public Law
  118-159), from the section heading to the source credit, against the section row's heading and
  body: section 67 has no word difference, only the adapter's spacing around punctuation ("2017 ,"
  versus "2017,", "( 15" versus "(15"); section 170 differs in that spacing, the HTML's
  line-break hyphenations ("sub section", "de scribed", "Commis sion", "deduc tion"), "§221" versus
  "§ 221", and the USLM footnote rule and texts ("So in original. Probably should be followed by ..."
  and "See References in Text note below."). The latest amendment notes are 2017 (Pub. L. 115-97, adding 67(g))
  and 2024 (Pub. L. 118-146, adding 170(b)(1)(A)(x) and (c)(6)); neither page lists a 2025 amendment.

Expression date and `source_as_of` are the release point's date, 2024-12-23, the same convention as
the 119-103 scopes.

Row identity: like every `extract-usc` scope, the JSONL rows carry the path-only `id`
(`uuid5(URL, "axiom:<citation_path>")`), so `us/statute/26/67` has the same `id`,
`f7e86439-2d9e-5eb1-89ed-707373af39a3`, in this scope and in the recovery scope.
`provision_to_supabase_row` (`src/axiom_corpus/corpus/supabase.py`) replaces a path-only `id` with
the versioned uuid5 of `["axiom", version, citation_path]` when it stages rows, so the two vintages
stage as distinct `corpus.provisions` rows told apart by `version` and `expression_date`.

Encoder caution: OBBBA redesignated subsections of 67, so one citation path names different text in
the two vintages. `us/statute/26/67/g` is "Suspension for taxable years 2018 through 2025" here and
"Educator expenses" in the recovery scope. The recovery scope holds 130 rows for 67 and 170 and this
vintage 506; they share 126 paths. Of those, 15 differ in body text (`67`, `67/b`, `67/b/11`,
`67/b/12`, `67/g`, `170`, `170/b`, `170/b/1`, `170/b/2`, `170/d`, `170/d/1`, `170/d/2`, `170/n`,
`170/n/1`, `170/p`) and one also in heading (`67/g`). `67/b/13`, `67/g/1`, `67/g/2` and `67/h` exist
only in the recovery scope; 380 paths of this vintage (for example `170/b/1/G`) have no current-text
row in the corpus.

### Why OLRC USLM, not the GovInfo HTML

The work order names the GovInfo USCODE-2024 section HTML "or the official annual USC XML". GovInfo
serves no XML for USCODE-2024-title26 (its package summary lists PDF, HTML, MODS, PREMIS and zip
only, and the two `/xml/` paths tried redirect to `https://www.govinfo.gov/error`). The
repository's GovInfo precedent
(`manifests/us-usc-26-85.yaml`, `extract-official-documents` with `anchor_range`) yields a single
section row (plus a document container row), while the recovery scope holds the current text of 67 and 170 at section, subsection and
paragraph level; a section-only vintage could not answer a citation such as `us/statute/26/170/b/1`
or `us/statute/26/170/b/1/G`.
OLRC is the same official publisher as every held `us/statute` scope, its release-point XML goes
through the same adapter as the 119-103 scope, and the GovInfo text was used as the comparison above.

### `extract-usc --prior-release-point`

`extract-usc` gives every row `source_url` equal to the current preliminary-edition reader page
(`view.xhtml?...edition=prelim`), which would display the post-OBBBA text for rows of this vintage. The
new flag (keyword `prior_release_point` of `extract_usc`, default off) sets `source_url` on every
inventory item and provision row to `--source-url`, the release point download whose bytes are
retained, and requires it. Impact: GitNexus `impact` upstream on `extract_usc` (newest local
axiom-corpus index, 2026-09-06, which predates this worktree) reports risk MEDIUM with 7 direct
callers, `_cmd_extract_usc` and six tests, and 0 affected processes; `_cmd_extract_usc` itself has
no static callers (argparse dispatch). `git grep -w extract_usc` on this worktree agrees:
`cli.py` plus `tests/test_corpus_usc.py` and `tests/test_corpus_cli.py`. The keyword is additive
and off by default, so every existing caller keeps its behaviour. Tests:
`test_extract_usc_prior_release_point_links_rows_to_the_release_point_download`,
`test_extract_usc_default_rows_keep_the_prelim_reader_url`,
`test_extract_usc_prior_release_point_requires_the_download_url`,
`test_extract_usc_cli_prior_release_point_passes_through`. `docs/corpus-pipeline.md` documents it.

## Commands

```bash
B=data/corpus
# 402A, 662, 852 (current text, release point 119-103)
uv run axiom-corpus-ingest extract-usc --base $B --version 2026-09-23-tax-statute-policybench \
  --source-zip $B/sources/us/statute/2026-09-13-tax-statute-closure-31-title-26/olrc/xml_usc26@119-103.zip \
  --title 26 --source-as-of 2026-09-02 --expression-date 2026-09-02 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/119/103/xml_usc26@119-103.zip \
  --section 662 --section 852 --section 402A
uv run python scripts/self_contain_usc_scope.py --base $B --version 2026-09-23-tax-statute-policybench-title-26

# 67, 170 (2024 vintage, prior release point 118-209 except 118-159)
uv run axiom-corpus-ingest extract-usc --base $B --version 2026-09-23-tax-statute-policybench-rp-118-209 \
  --source-zip xml_usc26@118-209not159.zip \
  --title 26 --source-as-of 2024-12-23 --expression-date 2024-12-23 \
  --source-url https://uscode.house.gov/download/releasepoints/us/pl/118/209not159/xml_usc26@118-209not159.zip \
  --prior-release-point --section 67 --section 170
uv run python scripts/self_contain_usc_scope.py --base $B --version 2026-09-23-tax-statute-policybench-rp-118-209-title-26

# coverage, per scope
uv run --extra dev axiom-corpus-ingest coverage --base $B \
  --source-inventory $B/inventory/us/statute/<scope>.json \
  --provisions $B/provisions/us/statute/<scope>.jsonl \
  --jurisdiction us --document-class statute --version <scope> --write
```

`extract-usc` appends `-title-26` to `--version` (`usc_run_id`), as in the 2026-09-13 scopes.

Reproduction check (2026-09-23T16:16Z onward): the 118-209 zip was downloaded again from the URL
above (SHA-256 `92e448a6...83148`, byte-identical to the retained file), and both scopes were
re-extracted with the commands above into a scratch base. All six inventory, provisions and
coverage files are byte-identical to the ones here once the scratch copy's local zip filename is
mapped to `xml_usc26@118-209not159.zip` (the adapter names the retained source after the local
file). The `coverage --write` command above rewrote both coverage reports with unchanged bytes.

Second, independent verification pass (2026-09-23T17:01Z to 17:16Z; all times in this note are UTC
on the host clock, the clock that stamped the scratch files): the 118-209 zip (17:01:41Z)
and the 119-103 zip (17:14:34Z) were downloaded again from the URLs above and hash to the retained
files' SHA-256; 118-274 and 119-110 hash to the values in the comparison table. With the
freshly downloaded 118-209 zip (saved under its publisher filename), both scopes re-extract to
byte-identical source, inventory, provisions and coverage files (all eight). The 118-274 and
119-110 comparisons, the GovInfo word-level comparison, the recovery-scope overlap counts, the
citation-path ratchet counts and the three release validations below were each rerun and gave the
results recorded here.

Third verification pass (2026-09-23T18:01Z to 18:11Z): the 118-209 zip (finished 18:06Z) and the
119-103 zip (finished 18:09Z) were downloaded again and hash to the retained files' SHA-256. Both
scopes re-extract (the 119-103 scope from the retained zip, the 118-209 scope from the fresh
download) to byte-identical source, inventory, provisions and coverage files, and `coverage --write`
leaves both coverage reports byte-identical. The prior release points page, fetched again, lists
118-233 (01/04/2025, the next release point after 118-209) as affecting titles 1, 5, 16, 30, 38, 40,
42, 43 and 48, not 26. The GovInfo pages hash to the values in the comparison table, and the
word-level comparison, the citation-path validator and the three release validations give the
results recorded here.

## Release validation

| Selector | Scopes | Result |
| --- | ---: | --- |
| `docs/ingest-runs/2026-09-23-tax-statute-policybench.selector.json` (predecessor `us-rulespec-2026-09-14-wave4-r2-union` plus the 402A/662/852 scope) | 1,043 | `ok: true`, 0 errors, 546 warnings, none naming a 2026-09-23 scope |
| same plus the 67/170 vintage (scratch, not tracked) | 1,044 | `ok: false`, 126 `duplicate_release_citation` errors, all in the vintage scope (for example "citation_path us/statute/26/67 is also present in us/statute/2026-07-13-recovery-r2026-07-15-self-contained-r2026-07-17-dedup") |
| the 67/170 vintage alone (scratch, not tracked) | 1 | `ok: true`, 0 errors, 0 warnings |

Command: `uv run axiom-corpus-ingest validate-release --base data/corpus --release <selector>
--ignore-r2-missing --max-issues 2000`. The 546 warnings are 541 `missing_parent_id` in
`us-ca/regulation/2026-07-13-recovery` and 5 `unsectioned_document_body` in WIC manuals and Iowa
forms.

The vintage therefore cannot join a union release that also selects the recovery scope. A selector
may carry it without the recovery scope, but activating such a release repoints the whole
`(us, statute)` serving pair to that release's scopes (`docs/named-release-publication.md`), so it
would have to be published and never activated, or wait for a vintage-aware serving design.

## Citation-path grammar

`scripts/validate_citation_paths.py` failed on the `uppercase_segments` ratchet (16,280 live against a
15,642 baseline). Without the two new provisions files the live count is exactly 15,642; the new
scopes add 638 unique uppercase paths, all US Code subparagraph letters and the section number 402A,
the category the schema documents ("US Code subsection letters"). The baseline in
`schema/citation-path.v1.json` is raised to 16,280 and the validator then passes (`ok: true`, no
pattern failures, no identity drift). Other branches that also raise this ceiling will conflict on
that line; recompute it on merge.

## Not done

- Nothing is committed, signed or published. `data/` is gitignored, so the eight scope paths
  (coverage, inventory, provisions, `sources/us/statute/<scope>/`) must be force-added, and CI's
  `guard-ingested` requires signed ingest manifests under `.axiom/ingest-manifests/us/statute/`
  (`axiom-corpus-ingest sign-ingest-manifest`, which needs `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and a
  clean committed tree).
- No selector under `manifests/releases/`; the draft stays under `docs/ingest-runs/`.
