# Unemployment insurance benefits, wave 1b and wave 2: regulations, agency documents, Kentucky, California, DC

Date: 2026-11-24 (America/New_York). Branch `ingest/ui-benefits-tier1-wave1b`, stacked on
`ingest/ui-benefits-tier1-wave1` (`docs/ingest-runs/2026-11-24-ui-benefits-wave1.md`).

Input: the roadmap's UI scope audit (`axiom-roadmap-dashboard` a9a977bc). No person reviewed it; each citation was
checked against the fetched official text. Nothing was signed, locked, loaded, pushed to R2 or published.

## Method

- Agency documents and most regulations: `extract-official-documents`, one manifest per jurisdiction and class
  (`manifests/us-<st>-ui-benefits-<class>.yaml`, written by `scripts/build_ui_benefits_document_manifests.py`).
- Regulations with an adapter: `extract-washington-wac` (WAC 192-170, 192-180, 192-190),
  `extract-oregon-administrative-rules` (OAR 471-030), `extract-illinois-admin-code` (56 Ill. Adm. Code 2865, 2920),
  `extract-maryland-comar` (COMAR 09.32.02, publication 2026-11-20).
- Every document's text was read for an empty body, page navigation and challenge pages. A document that failed that
  reading is in the generator's `HELD` list with its reason and is in no manifest.
- Titles of statutes and regulations are the headings the official text prints, not the audit's.
- `scripts/validate_citation_paths.py` over the new provisions files: `RESULT: OK`.
- TLS: `REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>`, full verification.

## Held documents (fetched, not kept)

| path | reason |
| --- | --- |
| `us-ne/regulation/title-219/chapter-4`, `chapter-7` | image-only PDF, no text layer; needs OCR |
| `us-sd/regulation/arsd/47/06/04` | the Legislature API serves UTF-16 HTML, which the document extractor reads as raw markup |
| `us-sd/guidance/dlr/ra/wage-requirements` | page navigation in the body; needs a content selector |
| `us-mi/guidance/uia/eligibility-requirements`, `us-mi/guidance/leo/news/2025-12-18-...` | an unsupported-browser banner in the body; needs a content selector |
| `us-de/guidance/dol/unemployment-insurance/claimant-faqs` | page navigation in the body; needs a content selector |
| `us-il/guidance/ides/unemployment-insurance-benefit-handbook` | a contents page; the handbook is nine linked pages |
| `us-wi/guidance/dwd/ui/ucb-10-p-handbook-for-claimants` | a contents page; the handbook is eleven linked pages |
| `us-mn/guidance/deed/ui/after-you-apply` | a hub page with 223 characters; the handbook PDF holds the content |

Not fetched: 7 DCMR chapter 3 (dcregs.dc.gov serves a rule list, one download per rule); California title 22
regulations (the audit's address is govt.westlaw.com, which answered HTTP 403 to the audit's recheck; not tried).

## Differences from the audit

- **787 KAR 1:320** is "Priority of deductions from benefits" in the official text.
- **D.C. Code 51-107** is "Determination of amount and duration of benefits".
- **Kentucky regulations**: the page the audit cites holds only the expiry line; the text is the engrossed PDF the
  page links (`/law/kar/downloads/docs/<id>/document.engrossed.pdf`), taken as `download_url`.
- **Wisconsin DWD 127 to 129**: the cited page is a scrolling viewer; the chapter PDF it links is taken.
- **Alaska 8 AAC 85**: the audit's address prints one section; the same official print route gives the whole chapter
  (`secStart=8.85.010&secEnd=8.85.900`, 115 section headings).
- **Nebraska 219 NAC 4 and 7**: the audit cites the listing page; the chapter files are image-only PDFs (held).
- **Florida 73B-11**: the chapter's `.doc` file from flrules.org is taken, not the rule list.

## Scopes

43 scopes, 1,416 rows, 1,319 with text. Every scope reports coverage `complete: true`.
All are ready to sign; `content-check` runs only on locked scopes, so its findings come after the lock.

| jurisdiction | class | version | rows | rows with text | characters |
| --- | --- | --- | ---: | ---: | ---: |
| us-ak | guidance | `2026-11-24-ui-benefits-guidance-ak` | 67 | 65 | 35,199 |
| us-ak | regulation | `2026-11-24-ui-benefits-regulation-ak` | 2 | 1 | 138,034 |
| us-ca | guidance | `2026-11-24-ui-benefits-guidance-ca` | 59 | 56 | 126,761 |
| us-dc | guidance | `2026-11-24-ui-benefits-guidance-dc` | 35 | 32 | 35,625 |
| us-dc | statute | `2026-11-24-ui-benefits-statute-dc` | 6 | 3 | 65,383 |
| us-de | guidance | `2026-11-24-ui-benefits-guidance-de` | 38 | 37 | 82,835 |
| us-de | regulation | `2026-11-24-ui-benefits-regulation-de` | 12 | 11 | 42,728 |
| us-fl | guidance | `2026-11-24-ui-benefits-guidance-fl` | 94 | 92 | 68,461 |
| us-fl | regulation | `2026-11-24-ui-benefits-regulation-fl` | 2 | 1 | 53,445 |
| us-hi | guidance | `2026-11-24-ui-benefits-guidance-hi` | 32 | 30 | 39,863 |
| us-hi | regulation | `2026-11-24-ui-benefits-regulation-hi` | 60 | 59 | 168,041 |
| us-ia | guidance | `2026-11-24-ui-benefits-guidance-ia` | 32 | 30 | 60,580 |
| us-ia | regulation | `2026-11-24-ui-benefits-regulation-ia` | 49 | 48 | 198,429 |
| us-id | guidance | `2026-11-24-ui-benefits-guidance-id` | 62 | 58 | 69,115 |
| us-id | regulation | `2026-11-24-ui-benefits-regulation-id` | 8 | 7 | 18,943 |
| us-il | guidance | `2026-11-24-ui-benefits-guidance-il` | 38 | 37 | 146,482 |
| us-il | regulation | `2026-11-24-ui-benefits-regulation-title-056-part-02865` | 23 | 18 | 57,141 |
| us-il | regulation | `2026-11-24-ui-benefits-regulation-title-056-part-02920` | 28 | 23 | 69,131 |
| us-ky | guidance | `2026-11-24-ui-benefits-guidance-ky` | 66 | 64 | 107,626 |
| us-ky | regulation | `2026-11-24-ui-benefits-regulation-ky` | 9 | 6 | 16,014 |
| us-ky | statute | `2026-11-24-ui-benefits-statute-ky` | 18 | 12 | 29,772 |
| us-md | guidance | `2026-11-24-ui-benefits-guidance-md` | 25 | 24 | 51,440 |
| us-md | regulation | `2026-11-24-ui-benefits-regulation-publication-2026-11-20-title-09-subtitle-32-chapter-02` | 26 | 22 | 42,969 |
| us-me | guidance | `2026-11-24-ui-benefits-guidance-me` | 36 | 34 | 96,186 |
| us-me | regulation | `2026-11-24-ui-benefits-regulation-me` | 6 | 3 | 37,057 |
| us-mi | guidance | `2026-11-24-ui-benefits-guidance-mi` | 31 | 30 | 59,440 |
| us-mn | guidance | `2026-11-24-ui-benefits-guidance-mn` | 29 | 28 | 34,304 |
| us-ne | guidance | `2026-11-24-ui-benefits-guidance-ne` | 4 | 2 | 2,098 |
| us-or | guidance | `2026-11-24-ui-benefits-guidance-or` | 79 | 76 | 91,703 |
| us-or | regulation | `2026-11-24-ui-benefits-regulation-chapter-471-division-30` | 62 | 59 | 122,040 |
| us-ri | guidance | `2026-11-24-ui-benefits-guidance-ri` | 7 | 4 | 12,070 |
| us-ri | regulation | `2026-11-24-ui-benefits-regulation-ri` | 2 | 1 | 84,025 |
| us-sc | guidance | `2026-11-24-ui-benefits-guidance-sc` | 34 | 32 | 78,166 |
| us-sc | regulation | `2026-11-24-ui-benefits-regulation-sc` | 33 | 32 | 127,057 |
| us-sd | guidance | `2026-11-24-ui-benefits-guidance-sd` | 23 | 22 | 51,560 |
| us-tx | guidance | `2026-11-24-ui-benefits-guidance-tx` | 77 | 75 | 72,565 |
| us-tx | regulation | `2026-11-24-ui-benefits-regulation-tx` | 91 | 90 | 198,337 |
| us-wa | guidance | `2026-11-24-ui-benefits-guidance-wa` | 46 | 44 | 71,632 |
| us-wa | regulation | `2026-11-24-ui-benefits-regulation-192-170` | 14 | 11 | 15,038 |
| us-wa | regulation | `2026-11-24-ui-benefits-regulation-192-180` | 13 | 10 | 17,920 |
| us-wa | regulation | `2026-11-24-ui-benefits-regulation-192-190` | 21 | 18 | 12,467 |
| us-wi | guidance | `2026-11-24-ui-benefits-guidance-wi` | 7 | 5 | 12,511 |
| us-wi | regulation | `2026-11-24-ui-benefits-regulation-wi` | 10 | 7 | 46,676 |

The seven adapter regulation scopes (Illinois, Maryland, Oregon, Washington) each hold one root container row
(`us-<st>/regulation`) whose path a scope of the pin-line selector also holds. Check `validate-release` for a
duplicate-path finding when the selector is cut.

## Wave 2

- **Kentucky**: no statute adapter. KRS 341.080, 341.090, 341.350, 341.380, 341.385 and 341.390 are taken as six
  official documents (the Legislature's section PDFs), with the three regulations and two agency documents.
- **District of Columbia**: D.C. Code 51-101, 51-107 and 51-109 are taken as official documents from the Council's law
  library (the `dc-code` adapter needs a checkout of the Council's law XML). Three agency documents. 7 DCMR chapter 3
  is not taken.
- **California**: see "California" below.

## California

leginfo.legislature.ca.gov answered HTTP 403 (a challenge page) to the corpus client on 2026-11-24, as in October.
Nothing was tried against it. The Legislative Counsel's own bulk host answered: `pubinfo_2025.zip` (1,292,279,927
bytes, dated 2026-11-22) from https://downloads.leginfo.legislature.ca.gov/, read with the existing
`extract-california-codes --only-title UIC`.

- Scope `us-ca/statute/2026-11-24-ui-benefits-statute-us-ca-title-UIC`: 1,266 rows, 1,115 with text, 1,320,564 characters; coverage complete.
- All 13 sections the audit cites (1252, 1253, 1254, 1255.3, 1255.5, 1265, 1265.5, 1265.6, 1275, 1276, 1279, 1280,
  1281) are present with text at `us-ca/statute/uic/<section>`.
- **Held:** the scope name carries the code in upper case (`title-UIC`), which the lock rule rejects, as for Texas.
  The fix is the same: a lower-case code token in the run id, or a lower-case successor scope.
- California title 22 regulations: not taken (the audit's address is a Westlaw host).
- Three EDD documents are taken (DE 1275A, DE 8714AB, the eligibility page).

Rebuild: download `pubinfo_2025.zip`, then
`uv run axiom-corpus-ingest extract-california-codes --base data/corpus --version 2026-11-24-ui-benefits-statute --source-zip pubinfo_2025.zip --source-url https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip --only-title UIC --source-as-of 2026-11-24 --expression-date 2026-11-22`.

## Adapter defects from wave 1: the fix for each (no adapter was changed)

| adapter | defect | fix | size |
| --- | --- | --- | --- |
| `texas-tcas` | the scope name carries the code in upper case (`title-LA`); the lock rule rejects it | pass `_texas_code_token(only_code)` (lower case) to `state_run_id` in `extract_texas_tcas`; one test | one line and a test |
| `south-dakota-codified-laws` | a listing entry "61-6-1.2, 61-6-1.3. Transferred ..." is read as section 61-6-1 with the heading ".2, 61-6-1.3. ...", and it replaces the live section | let `_SECTION_LABEL_RE` take a decimal suffix and a comma-joined list, one row per label; never let a row without text replace a row with text at one path | half a day with tests |
| `missouri-revised-statutes` | the full-chapter page omits a section the chapter index lists (288.036); the run stops | for a listed section the full-chapter page omits, read its own `OneSection.aspx` page (the adapter already builds that address), or record a coverage gap; keep both enactments of 288.060 as variants | about one day |
| `north-dakota-code` | `_scope_filter` accepts only chapter 57-38, and the module carries income-tax schedule inputs | take the chapter from the filter (`t52c06.pdf`, `t52c01.pdf`), make the schedule inputs optional, generalise the 21 fixed `57-38` references | one to two days |
| official-document extractor | UTF-16 HTML (South Dakota rules API) is read as raw markup | decode by BOM or `charset` before parsing | small |

## Human steps

1. Sign and lock the wave 1 scopes first (`docs/ingest-runs/2026-11-24-ui-benefits-wave1.md`), then these, with
   `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and R2 write access:

   ```bash
   tail -n +2 docs/ingest-runs/2026-11-24-ui-benefits-wave1b-unsigned-scopes.tsv |
   while IFS=$'\t' read -r j c v note; do
     uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction "$j" --document-class "$c" --version "$v" \
       --command "rebuild: see $note" --lock --push < /dev/null || break
   done
   git add .axiom/ingest-manifests .axiom/corpus-locks
   ```

2. Run `content-check` on the locked scopes; record or fix its findings.
3. Add the scopes to the successor selector of wave 1
   (`docs/ingest-runs/2026-11-24-us-rulespec-ui-benefits-wave1.selector.json`) before it is cut. Publish only.

The artifacts are in the worktree's `data/corpus` and in a copy under `~/.axiom/workspace/ui-benefits-2026-11-24`.

## Rebuild

```bash
B=data/corpus; export REQUESTS_CA_BUNDLE=<certifi + data/certs/*.pem>
uv run python scripts/build_ui_benefits_document_manifests.py
for m in manifests/us-*-ui-benefits-{guidance,regulation}.yaml manifests/us-{dc,ky}-ui-benefits-statute.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --manifest $m \
    --version "$(grep -m1 '^version:' $m | awk '{print $2}')"
done
V=2026-11-24-ui-benefits-regulation; D="--source-as-of 2026-11-24 --expression-date 2026-11-24"
for c in 192-170 192-180 192-190; do
  uv run axiom-corpus-ingest extract-washington-wac --base $B --version $V --only-title 192 --only-chapter $c $D
done
uv run axiom-corpus-ingest extract-oregon-administrative-rules --base $B --version $V --only-chapter 471 --only-division 30 $D
for p in 2920 2865; do
  uv run axiom-corpus-ingest extract-illinois-admin-code --base $B --version $V --only-title 56 --only-part $p $D
done
uv run axiom-corpus-ingest extract-maryland-comar --base $B --version $V --only-title 09 --only-subtitle 32 --only-chapter 02 $D
```

Impact analysis: the GitNexus tools were not available in this session; no library code changed in this run.
