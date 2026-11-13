# State child care subsidy income limits and the October 2026 Georgia CAPS manual

Date: 2026-11-13. Branch `ingest/child-care-income-limits-2026-11`, cut from `origin/main` `8d8076b82`.

- Ten scopes hold 28 documents and 978 provision rows. The extractor fetched each document live
  from its publisher's URL.
- Manifests: `manifests/us-{al,id,in,mo,nv,oh}-ccdf-income-limits-2026-11.yaml`,
  `manifests/us-ga-caps-manual-2026-10-05.yaml`, `manifests/us-ga-caps-notices-2026-11.yaml`,
  `manifests/us-mt-ccdf-income-limits-2026-11.yaml` and
  `manifests/us-mt-ccdf-income-limits-statute-2026-11.yaml`.

## Why

PolicyEngine/policyengine-us#10670 sets child care subsidy income limits to the figures each state
posts. The rulespec-us parity issues it files cite each limit's source by corpus path, and no scope
held these documents. Two citations already sit in the corpus but off the rulespec-us pin line:

- ARM 37.80.202, Montana's 150% and 185% FPG tests, at
  `us-mt/regulation/title-37/chapter-37-80/subchapter-37-80-2/rule-37-80-202` (version 49811,
  effective 2020-06-01) in
  `us-mt/regulation/2026-09-14-income-tax-regulations-title-42-section-42-15-r2026-10-07-w6-37-78-37-80-sans-420-consolidated`.
- Georgia's CCDF plan for FFY 2025-2027 in `us-ga/policy/2026-09-13-ccdf-plan-fy2025-2027`.

This run adds neither.

## Commands

We ran one command per scope from the repository root:

```
axiom-corpus-ingest extract-official-documents --base data/corpus --version <version> --manifest manifests/<manifest>.yaml
```

| Scope | Version | Manifest |
| --- | --- | --- |
| `us-al/policy` | `2026-11-13-ccdf-income-limits` | `us-al-ccdf-income-limits-2026-11.yaml` |
| `us-ga/manual` | `2026-11-13-ga-caps-2026-10-05` | `us-ga-caps-manual-2026-10-05.yaml` |
| `us-ga/policy` | `2026-11-13-ccdf-income-limits` | `us-ga-caps-notices-2026-11.yaml` |
| `us-id/policy` | `2026-11-13-ccdf-income-limits` | `us-id-ccdf-income-limits-2026-11.yaml` |
| `us-in/policy` | `2026-11-13-ccdf-income-limits` | `us-in-ccdf-income-limits-2026-11.yaml` |
| `us-mo/policy` | `2026-11-13-ccdf-income-limits` | `us-mo-ccdf-income-limits-2026-11.yaml` |
| `us-mt/policy` | `2026-11-13-ccdf-income-limits` | `us-mt-ccdf-income-limits-2026-11.yaml` |
| `us-mt/statute` | `2026-11-13-ccdf-income-limits` | `us-mt-ccdf-income-limits-statute-2026-11.yaml` |
| `us-nv/policy` | `2026-11-13-ccdf-income-limits` | `us-nv-ccdf-income-limits-2026-11.yaml` |
| `us-oh/policy` | `2026-11-13-ccdf-income-limits` | `us-oh-ccdf-income-limits-2026-11.yaml` |

## Scopes

Every scope's coverage report reads complete, with no missing, extra or duplicate citation paths.
Each document row's `expression_date_basis` names the source of its date.

### `us-al/policy/2026-11-13-ccdf-income-limits`

2 documents, 4 provision rows, 4 inventory items; coverage complete, matched 4, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-al/policy/dhr/ccdf/child-care-fact-sheet-2026-01` | 2026-01-01 | 2 | 253,907 | `08599174be9d…` |
| `us-al/policy/dhr/ccdf/child-care-fact-sheet-2026-06` | 2026-06-01 | 2 | 199,423 | `e08a22eb3a49…` |

Sources:

- `child-care-fact-sheet-2026-01`: https://dhr.alabama.gov/wp-content/uploads/2025/12/CHILD-CARE-FACT-SHEET-Jan2026.pdf
- `child-care-fact-sheet-2026-06`: https://dhr.alabama.gov/wp-content/uploads/2026/06/CHILD-CARE-FACT-SHEET-Jun2026-1.pdf

### `us-ga/manual/2026-11-13-ga-caps-2026-10-05`

2 documents, 114 provision rows, 114 inventory items; coverage complete, matched 114, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-ga/manual/decal/caps/policy-manual` | 2026-10-05 | 112 | 2,100,349 | `24603b1ce662…` |
| `us-ga/manual/decal/caps/appendix-a-income-limits` | 2026-10-05 | 2 | 165,475 | `83b123ab9b0c…` |

Sources:

- `policy-manual`: https://caps.decal.ga.gov/assets/downloads/CAPS/0-CAPS_Policy-Manual.pdf
- `appendix-a-income-limits`: https://caps.decal.ga.gov/assets/downloads/CAPS/AppendixA-CAPS%20Maximum%20Income%20Limits%20by%20Family%20Size.pdf

### `us-ga/policy/2026-11-13-ccdf-income-limits`

10 documents, 38 provision rows, 38 inventory items; coverage complete, matched 38, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-ga/policy/decal/caps/funding-restrictions-qa-2016` | 2016-08-01 | 3 | 288,568 | `2ecdb27a65f8…` |
| `us-ga/policy/decal/caps/provider-letter-2018-06-18` | 2018-06-18 | 2 | 536,857 | `4500232839a5…` |
| `us-ga/policy/decal/caps/policy-webinar-2019-07` | 2019-07-01 | 14 | 1,902,634 | `536a5df97377…` |
| `us-ga/policy/decal/caps/family-letter-2021-10-21` | 2021-10-21 | 2 | 124,075 | `273788fe6841…` |
| `us-ga/policy/decal/caps/family-letter-2022-12-19` | 2022-12-19 | 2 | 139,469 | `0ffbc9e5788b…` |
| `us-ga/policy/decal/caps/emergency-policy-memorandum-2024-10-01` | 2024-10-01 | 4 | 174,152 | `9807415cdabf…` |
| `us-ga/policy/decal/caps/family-letter-2024-07-01` | 2024-07-01 | 3 | 125,581 | `fcf4c74b3647…` |
| `us-ga/policy/decal/caps/family-letter-2024-09-03` | 2024-09-03 | 2 | 115,219 | `55b20d6bcafe…` |
| `us-ga/policy/decal/caps/family-letter-2025-10-06` | 2025-10-06 | 3 | 240,189 | `3350baa45fdf…` |
| `us-ga/policy/decal/caps/family-letter-2026-03-02` | 2026-03-02 | 3 | 180,470 | `a5d971c7bdd2…` |

Sources:

- `funding-restrictions-qa-2016`: https://www.decal.ga.gov/documents/attachments/fundingrestrictionsqa.pdf
- `provider-letter-2018-06-18`: https://caps.decal.ga.gov/assets/downloads/CAPS_Letter_from_Elisabetta_Kasfir_6-18-2018.pdf
- `policy-webinar-2019-07`: http://caps.decal.ga.gov/Assets/downloads/CAPS_Policy_Webinar_for_Child_Care_Providers_7-10-19.pdf (bytes from https://caps.decal.ga.gov/Assets/downloads/CAPS_Policy_Webinar_for_Child_Care_Providers_7-10-19.pdf)
- `family-letter-2021-10-21`: https://caps.decal.ga.gov/assets/downloads/CAPS_Letter_from_Elisabetta_Kasfir_Families_10-21-21.pdf
- `family-letter-2022-12-19`: https://caps.decal.ga.gov/assets/downloads/CAPS_Letter_to_Parents_Change_in_Income_Limits_12.19.2022.pdf
- `emergency-policy-memorandum-2024-10-01`: https://caps.decal.ga.gov/assets/downloads/CAPS_Emergency_Policy_Memorandum.pdf
- `family-letter-2024-07-01`: https://caps.decal.ga.gov/Assets/downloads/CAPS_Letter_from_Elisabetta_Kasfir_Families_07.01.2024.pdf
- `family-letter-2024-09-03`: https://caps.decal.ga.gov/Assets/downloads/CAPS_Letter_from_Elisabetta_Kasfir_Families_09.03.2024.pdf
- `family-letter-2025-10-06`: https://caps.decal.ga.gov/Assets/downloads/CAPS_Letter_to_Families_Policy_Revisions_10.06.25.pdf
- `family-letter-2026-03-02`: https://caps.decal.ga.gov/Assets/downloads/CAPS_Letter_to_Families_Policy_Revisions_03.02.26.pdf

### `us-id/policy/2026-11-13-ccdf-income-limits`

2 documents, 7 provision rows, 7 inventory items; coverage complete, matched 7, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-id/policy/dhw/ccdf/iccp-applications-resume-2025-01-13` | 2024-11-14 | 2 | 164,489 | `7f927024a95c…` |
| `us-id/policy/dhw/ccdf/apply-for-child-care` | 2025-10-01 | 5 | 178,255 | `419caac68780…` |

Sources:

- `iccp-applications-resume-2025-01-13`: https://healthandwelfare.idaho.gov/news/dhw-will-resume-applications-idaho-child-care-program-january
- `apply-for-child-care`: https://healthandwelfare.idaho.gov/services-programs/children-families/apply-child-care (bytes from https://healthandwelfare.idaho.gov/services-programs/children-families-older-adults/apply-child-care-assistance)

### `us-in/policy/2026-11-13-ccdf-income-limits`

1 document, 247 provision rows, 247 inventory items; coverage complete, matched 247, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-in/policy/fssa/oecosl/ccdf-plan-fy2025-2027-amendment-2` | 2025-11-14 | 247 | 3,150,811 | `85f25fed5672…` |

Sources:

- `ccdf-plan-fy2025-2027-amendment-2`: https://www.in.gov/dA/6307709ae5/ACF-118CCDFFFY2025-2027IndianaAmendment.pdf?language_id=1

### `us-mo/policy/2026-11-13-ccdf-income-limits`

1 document, 2 provision rows, 2 inventory items; coverage complete, matched 2, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-mo/policy/dese/ccdf/income-eligibility-table-2026-07` | 2026-07-01 | 2 | 146,996 | `efb37b48e38b…` |

Sources:

- `income-eligibility-table-2026-07`: https://dese.mo.gov/sites/g/files/zuston521/files/media/pdf/2026/07/Income%20Elig%20_Updated%206.29.26.pdf

### `us-mt/policy/2026-11-13-ccdf-income-limits`

1 document, 15 provision rows, 15 inventory items; coverage complete, matched 15, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-mt/policy/lfd/child-care-overview-2024-06` | 2024-06-18 | 15 | 221,258 | `d1aa768469b7…` |

Sources:

- `child-care-overview-2024-06`: https://leg.mt.gov/content/Publications/fiscal/2025-Biennium/Special-Topics/Childcare/Childcare-Overview-LEG-Days-June2024.pdf (bytes from https://archive.legmt.gov/content/Publications/fiscal/2025-Biennium/Special-Topics/Childcare/Childcare-Overview-LEG-Days-June2024.pdf)

### `us-mt/statute/2026-11-13-ccdf-income-limits`

1 document, 2 provision rows, 2 inventory items; coverage complete, matched 2, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-mt/statute/52-2-715` | 2026-11-13 | 2 | 10,598 | `0f1e6c745718…` |

Sources:

- `52-2-715`: https://mca.legmt.gov/bills/mca/title_0520/chapter_0020/part_0070/section_0150/0520-0020-0070-0150.html

### `us-nv/policy/2026-11-13-ccdf-income-limits`

5 documents, 501 provision rows, 501 inventory items; coverage complete, matched 501, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-nv/policy/ccdf/policy-transmittals/ccdp-annual-income-changes-2026` | 2026-10-01 | 5 | 861,558 | `b972df2458d2…` |
| `us-nv/policy/ccdf/state-plan/ffy2022-2024-draft` | 2021-10-01 | 181 | 2,914,153 | `d1ffaa847b22…` |
| `us-nv/policy/ccdf/state-plan/ffy2022-2024-amended` | 2022-07-01 | 307 | 3,289,268 | `047d4abff319…` |
| `us-nv/policy/ccdf/notices/child-care-updates-parents-2024-03-27` | 2024-03-27 | 3 | 232,378 | `9047cd6b10e9…` |
| `us-nv/policy/ccdf/notices/copayment-webinar-qa-2024-11` | 2024-11-13 | 5 | 361,855 | `24275f9f08be…` |

Sources:

- `ccdp-annual-income-changes-2026`: https://prod.dss.nv.gov/siteassets/dwss.nv.gov/ccdp-annual-income-changes-2026_1.pdf
- `ffy2022-2024-draft`: https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Home/Features/2022-2024%20Child%20Care%20PrePrint%20Draft%281%29.pdf (bytes from https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/home/features/2022-2024_Child_Care_PrePrint_Draft_1.pdf)
- `ffy2022-2024-amended`: https://dwss.nv.gov/uploadedFiles/dwssnvgov/content/Care/Amended%20State%20Plan.pdf (bytes from https://www.dss.nv.gov/siteassets/dwss.nv.gov/content/care/Amended_State_Plan.pdf)
- `child-care-updates-parents-2024-03-27`: https://www.nevadachildcare.org/static/200a0b5ae99f788e8c99d6f7824dc92b/Child-Care-Updates-Parents-.pdf
- `copayment-webinar-qa-2024-11`: https://www.nevadachildcare.org/static/bba7e54af87b3b89e51dd500b42629bf/Copayment-Webinar-QA_FINAL_NOV24.pdf

### `us-oh/policy/2026-11-13-ccdf-income-limits`

3 documents, 48 provision rows, 48 inventory items; coverage complete, matched 48, missing 0, extra 0, duplicate citation paths 0.

| Citation path | Expression date | Rows | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| `us-oh/policy/dcy/ccdf/procedure-letter-45` | 2026-10-01 | 8 | 1,234,986 | `2ced4d319dfc…` |
| `us-oh/policy/dcy/ccdf/procedure-letter-36` | 2025-11-01 | 5 | 253,141 | `c4726615ce79…` |
| `us-oh/policy/lsc/hb96/children-and-youth-final-analysis` | 2025-09-30 | 35 | 469,559 | `8fae3b08e865…` |

Sources:

- `procedure-letter-45`: https://dam.assets.ohio.gov/image/upload/childrenandyouth.ohio.gov/For%20Partners%20and%20Providers/Rules%20and%20Resources/2026/PL_45.pdf
- `procedure-letter-36`: https://dam.assets.ohio.gov/image/upload/childrenandyouth.ohio.gov/For%20Partners/Rules%20and%20Resources/2025/PL_36.pdf
- `children-and-youth-final-analysis`: https://www.lsc.ohio.gov/assets/legislation/136/hb96/en0/files/hb96-kid-bill-analysis-as-enacted-136th-general-assembly.pdf

## Notes on particular sources

- **Georgia CAPS manual.** `us-ga/manual/2026-11-13-ga-caps-2026-10-05` succeeds
  `us-ga/manual/2026-06-25-ga-caps` for the policy manual and Appendix A only, at the same citation
  paths. Georgia's Department of Early Care and Learning (DECAL) serves both at unchanged URLs. Appendix A now prints SMI thresholds effective
  October 5, 2026, and the manual's PDF carries the same creation date. The manual grew from 109
  pages to 111, so a `page-N` path here can hold different text from the predecessor's `page-N`.
  The other appendices stay with the predecessor scope.
- **Idaho.** The Department of Health and Welfare (DHW) moved its "Apply for Child Care" page; the old address answers 301. `source_url`
  keeps the address the parity issue cites, and `download_url` names the page's current address.
- **Nevada.** The FFY 2022-2024 CCDF plans' `dwss.nv.gov/uploadedFiles/...` addresses now redirect, in
  three steps, to `www.dss.nv.gov/siteassets/...`; `download_url` names that final address. The parent notice and the
  copayment Q&A come from nevadachildcare.org, the Child Care and Development Program site that the
  Division of Welfare and Supportive Services funds.
- **Montana statute.** No scope used the plain path `us-mt/statute/52-2-715`, which now holds the
  Montana Code Annotated 2025 text. The page embeds a script that changes on every request, so two
  captures differ in bytes; the statute text and history stay identical, and the provision rows
  carry no script.
- **Montana Legislative Fiscal Division overview.** The report prints no date. Its PDF metadata gives June 18, 2024, and its tables
  report fiscal 2024 spending to June 13, 2024.

## Left out

The parity issues also cite sources that no live official URL serves, so we left them out:

| Source | Why | Capture that holds it |
| --- | --- | --- |
| Indiana CCDF Sliding Fee Schedule with Copays, March 2023, March 2024 and March 2025 editions | `https://www.in.gov/fssa/carefinder/files/CCDFSlidingFeeSchedule_withCopays.pdf` now answers 404 | Internet Archive `20230501122705`, `20240413093550` and `20250403065234` |
| Maryland MSDE Child Care Scholarship Program page (income scales effective 12.15.2024) | Every URL on `earlychildhood.marylandpublicschools.org` redirects (302) to an Internet Archive capture of the site's home page | Internet Archive `20261009215322` |
| Georgia CAPS Appendix A editions, November 2020 through March 2026 | DECAL serves only the current edition | Internet Archive `20201124060600`, `20211026013823`, `20220301180356`, `20230304133123`, `20231208060145`, `20240520214500`, `20250301224420`, `20250308021446` and `20260308171215` |
| ACF, CCDF Family Income Eligibility Levels by State (January 2025) | acf.gov answers automated requests for it with an empty 202 response | none fetched |

We wrote manifests for the Indiana and Maryland captures in the form
`manifests/us-az-des-faa5-manual.yaml` uses (`source_url` official, `download_url` the `id_`
capture, plus `source_access_note`), and both extract with complete coverage. They can follow in
their own scopes if the corpus accepts Internet Archive captures for these sources.

## Citation-path ratchet

Run against every locked us-al, us-ga, us-id, us-in, us-mo, us-mt, us-nv and us-oh scope,
`scripts/validate_citation_paths.py` counts 6 `block_n` paths and 834 `page_n` paths in these
scopes that no locked scope held. The `block_n` paths come from the two Idaho DHW pages (five blocks) and
MCA 52-2-715 (one). Alabama adds 2 `page_n` paths, Georgia's notices 28, the Georgia manual 2, Indiana 246, Missouri 1,
Montana 14, Nevada 496 and Ohio 45. The October 2026 Georgia CAPS manual repeats 109 of
its predecessor's page paths and its Appendix A page, which the validator counts once.
`schema/citation-path.v1.json` raises `block_n` from 105419 to 105425 and `page_n` from 178888 to
179722; the merged-tree scan in PR CI checks both. The validator finds no pattern, jurisdiction,
document-class or identity failures in the new rows.
