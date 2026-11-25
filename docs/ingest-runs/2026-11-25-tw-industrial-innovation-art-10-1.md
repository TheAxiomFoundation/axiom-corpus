# tw: Statute for Industrial Innovation Art. 10-1 and its implementing regulation

Date: 2026-11-25. Version: `2026-11-25-tw-industrial-innovation`. First `tw` corpus presence.

## Why

Pilot: encode one Taiwan firm-level AI tax incentive (the Article 10-1 investment credit) in a
`rulespec-tw` repository and run it inside an external AI cost calculator for a CFO-type user.
The encoder needs the statute article and the regulation articles that set the computation.

## Sources

Both from the Ministry of Justice "Laws & Regulations Database of the Republic of China (Taiwan)"
(全國法規資料庫), the official consolidated Chinese text. The English pages under
`law.moj.gov.tw/ENG` are unofficial translations and are not captured.

| Scope | Instrument | pcode | Last amended (database header) | URL |
| --- | --- | --- | --- | --- |
| `tw/statute` | 產業創新條例 (Statute for Industrial Innovation), whole act | J0040051 | 2026-09-30 (民國 115 年 9 月 30 日) | https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0040051 |
| `tw/regulation` | 公司或有限合夥事業投資智慧機械與第五代行動通訊系統與資通安全人工智慧產品或服務及節能減碳抵減辦法 (MOEA with MOF, under Art. 10-1 para. 9) | J0040062 | 2025-11-27 (民國 114 年 11 月 27 日) | https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0040062 |

Not used: the data.gov.tw bulk law XML (dataset 18289). It holds every Taiwan law; this pilot
needs two.

## Extraction

Each page prints an article as `<div class="row">`, the number in `.col-no` (`第 10-1 條`) and the
paragraphs as `.law-article > div`. The manifests use `labeled_sections` with
`html_content_selector: .law-reg-content`, `html_text_selector: '.col-no, .law-article > div'` and
`section_label_pattern: '^第\s*(?P<label>\d+(?:-\d+)?)\s*條$'`, so a provision path is
`tw/statute/j0040051/10-1` or `tw/regulation/j0040062/9`. Chapter headings (`.h3`) are not
selected and do not enter article bodies. Deleted articles (`（刪除）`) are kept as rows.

```bash
for m in statute regulations; do
  uv run --extra dev axiom-corpus-ingest extract-official-documents \
    --base data/corpus --version 2026-11-25-tw-industrial-innovation \
    --manifest manifests/tw-industrial-innovation-$m-official-documents.yaml
done
```

A bounded smoke run (`--limit 3`, scratch base) gave the same counts before the full run.

## Counts and coverage

| Scope | Sources | Provisions (document + articles) | Matched | Complete |
| --- | ---: | ---: | ---: | --- |
| `tw/statute/2026-11-25-tw-industrial-innovation` | 88 | 88 (1 + 87) | 88 | true |
| `tw/regulation/2026-11-25-tw-industrial-innovation` | 22 | 22 (1 + 21) | 22 | true |

Spot checks: `tw/statute/j0040051/10-1` has all nine paragraphs (1,188 characters) and
`tw/regulation/j0040062/9` has all six paragraphs (938 characters) of the live pages.

## Artifact SHA-256 (local, not yet locked)

```text
7ba0b3d0e453db2e816215339430156292231611612c9fc7d3be3f5720e69643  sources/tw/statute/2026-11-25-tw-industrial-innovation/official-documents/tw-statute-for-industrial-innovation.html
77ca56df41327b4a36339ebeb42d6ef794c06a71459aebe41cfbbcedbb87228e  sources/tw/regulation/2026-11-25-tw-industrial-innovation/official-documents/tw-smart-investment-credit-regulation.html
4050f5bc6c01e922c41a67396a238d1638de47f75229677a81de8df878cefa07  inventory/tw/statute/2026-11-25-tw-industrial-innovation.json
3ddcdf413001e7bfc5dde2cc6108048d5408f8507fbb3583252a57605962f3d5  inventory/tw/regulation/2026-11-25-tw-industrial-innovation.json
6b8e187c6f8624642474a70dad4af8006a555363d45d4e8b82858902cd8993c4  provisions/tw/statute/2026-11-25-tw-industrial-innovation.jsonl
919228a53ce6e39ab8d073ad8268e6670407ef814f4591b76d1999227f2f317f  provisions/tw/regulation/2026-11-25-tw-industrial-innovation.jsonl
8dfc67f22cc98583bf962e7e11ab9cfc1716ee8a9ba551d5762418ebf1878318  coverage/tw/statute/2026-11-25-tw-industrial-innovation.json
627e1576ba8ab8269d0b5271dd93a3bceb8104a08714db5196531ad4e5590b53  coverage/tw/regulation/2026-11-25-tw-industrial-innovation.json
```

## Not done in this branch

- `sign-ingest-manifest --lock --push` for both scopes. Signing needs the ingest private key
  and a maintainer's approval; a new jurisdiction also needs Max's go-ahead (precedent: the
  Israel pilot, where merging was his decision).
- No release selector. Publication and activation are separate controller steps.
