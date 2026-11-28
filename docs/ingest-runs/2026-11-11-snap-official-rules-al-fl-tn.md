# SNAP rules for Alabama, Florida and Tennessee from the official publishers (2026-11-11)

## What was wrong

Four served scopes hold state SNAP rules as partial captures of Cornell LII pages:

| Scope | Rules | Manifest |
| --- | ---: | --- |
| `us-al/regulation/2026-05-29-r2026-07-15-self-contained` | 42 | `manifests/us-al-snap-primary-policy.yaml` |
| `us-fl/regulation/2026-05-29-r2026-07-15-self-contained` | 68 | `manifests/us-fl-snap-primary-policy.yaml` |
| `us-sc/regulation/2026-05-29-r2026-07-15-self-contained` | 19 | `manifests/us-sc-snap-primary-policy.yaml` |
| `us-tn/regulation/2026-05-29-r2026-07-15-self-contained` | 117 | `manifests/us-tn-snap-primary-policy.yaml` |

The manifests name `law.cornell.edu/regulations/...` as each rule's source, with the
note "used as a corpus normalization source pending a full official ... ingest". The
shared HTML extractor reads those pages badly:

- Every rule's `block-1` opens with the page's tabs, "State Regulations" and "Compare".
- Every `block-2` ("Notes") ends with the page's notice, "State regulations are updated
  quarterly; we currently have two versions available. ...".
- The capture stops at the first paragraph. A numbered list after it is lost. Fla. Admin.
  Code r. 65A-1.203 is held as one sentence; its 12 definitions are missing.
- The rows' `source_url` names the official site while `metadata.download_url` names the
  mirror.

A word-by-word comparison of the 201 rules that the SNAP bundles cite, against a second
copy of each rule (the OpenLaws API, used as a reference only), classed them:

| | Rules |
| --- | ---: |
| Repealed or reserved (no text on either side) | 56 |
| Complete | 28 |
| Partial (median 17% of the rule's words) | 57 |
| No rule text | 60 |

14 of these rules have an encoded provision. 11 of the 14 rest on incomplete text:
`us-al/regulation/660-4/2/03`, `2/06`, `2/11`, `2/12`, `7/05`, `7/08`;
`us-fl/regulation/fac/65a-1/711`; `us-tn/regulation/1240-01/03/15`, `03/46`, `04/07`,
`04/09`.

`manifests/release-content-baseline.json` records no finding for these scopes: the
content check reads navigation from the retained HTML, and these strings are tabs and a
notice inside the page's content area.

The other two manifests that read the mirror are already superseded in serving:
Massachusetts serves `2026-07-24-ma-dta-regulations-snap-current-union` (mass.gov) and
North Carolina serves `2026-05-29` (reports.oah.state.nc.us).

## What this run adds

Three manifests that read the official publishers. Each was extracted on 2026-11-11 with
`extract-official-documents` into a scratch base. Nothing is signed, locked, loaded or
selected.

| Manifest | Version | Source | Documents | Rows |
| --- | --- | --- | ---: | ---: |
| `us-fl-snap-fac-65a-1-official.yaml` | `2026-11-11-snap-official-rules-fl` | flrules.org, the final adopted rule file (`.doc`) of each rule | 31 | 62 |
| `us-al-snap-admin-code-660-4.yaml` | `2026-11-11-snap-official-chapters-al` | admincode.legislature.state.al.us, chapter PDFs 660-4-1 to -5 and -7 | 6 | 96 |
| `us-tn-snap-rules-1240-01-chapters.yaml` | `2026-11-11-snap-official-chapters-tn` | publications.tnsosfiles.com, chapter PDFs 1240-01-02, -03, -04, -08, -12, -14 | 6 | 132 |

Results:

- **Florida.** flrules.org has a rule file for 31 of the 68 rule numbers; the other 37 are
  repealed and have no current rule. The 31 keep the citation paths of the mirror rows
  (`us-fl/regulation/fac/65a-1/<rule>`). Their text grows from 1,924 words to 35,016. No
  row opens with the mirror's tabs.
- **Alabama.** All 33 live rules are in the chapter text: at least 90% of each rule's
  four-word sequences occur in its chapter's pages. Paths follow the held 660-2-2 and
  660-2-4 chapters: `us-al/regulation/alabama-administrative-code/660/4/<chapter>/page-N`.
- **Tennessee.** All 63 live rules are in the chapter text by the same measure. Paths
  follow the South Carolina chapter precedent: `us-tn/regulation/1240-01-<chapter>-pdf/page-N`.
- **South Carolina.** No new capture. `us-sc/regulation/2026-10-06-w6-tanf-ccdf-regulation-sc`
  already holds the official Chapter 114 PDF (`us-sc/regulation/chapter-114-pdf`), which
  contains Articles 13 and 27.

`tests/test_manifest_mirror_sources.py` freezes the six legacy manifests: no other
manifest may name `law.cornell.edu` as a `source_url` or `download_url`.

## What is left

1. Sign and lock the three scopes, then stage them.
2. Decide the paths for Alabama and Tennessee. The chapter PDFs are page-keyed, so the
   bundle rows and the encoded modules that cite `us-al/regulation/660-4/<c>/<rule>` and
   `us-tn/regulation/1240-01/<c>/<rule>` need either a per-rule split of the chapter text
   at those paths or a move to the page paths. Florida needs no decision.
3. Swap the scopes in at the next cut of each line that carries a predecessor, and drop
   the predecessor in the same edit. Point the South Carolina SNAP bundle rows at the
   Chapter 114 PDF.
4. Re-read the 11 encoded rules listed above after the release.
5. Consider a content-check finding for mirror page furniture inside the content area
   (a new check version and baseline).
