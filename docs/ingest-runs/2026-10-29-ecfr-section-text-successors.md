# eCFR section-text successor scopes

Date: 2026-10-29. Extractor baseline: `b92bd3033c0bed9c1b7ce9a1b37ff3d9476f69fb` (the merge of #832).

## Why

PR #832 makes eCFR section and appendix bodies keep table captions as `[Table caption: …]` blocks and separate words at `<br/>` and block boundaries. Earlier appendix output kept plain captions; the shared marker now lets the provision-anchor scanner mask an entire caption without changing body offsets. Locked scopes keep their exact bytes, so these seven new scope versions carry the merged rendering into future releases. This run changes no extractor source code.

## Native successor rule

Each successor runs the current native `extract-ecfr` command at its predecessor's own point in time. This run applies the rule to all seven scopes, including 47 CFR 54 and 45 CFR 1302. Those two native commands also carry earlier extractor repairs in 17 rows. The body-change tables distinguish those repairs from #832. No scope applies a narrower renderer-only patch to predecessor rows.

## Date and flag evidence

The [2026-09-13 federal CFR run note](2026-09-13-federal-cfr-layer.md) records `--as-of 2026-09-10 --expression-date 2026-09-10` for 26 CFR 31 and 42 CFR 407, 423 and 447, without appendices. Their signed ingest manifests carry generic `extract-official-documents` batch labels and references to earlier run notes; those labels supply no point-in-time arguments. The native eCFR run note supplies the date and selection evidence.

The [part 404 appendix run note](2026-10-12-cfr-404-subpart-appendices.md) records `--as-of 2026-10-08 --expression-date 2026-10-08 --include-appendices` for its whole-part successor. This run keeps those arguments.

The [original 47 CFR 54 signed manifest](../../.axiom/ingest-manifests/us/regulation/2026-06-18-title-47-part-54.json) records native `extract-ecfr --version 2026-06-18 --as-of 2026-06-18 --only-title 47 --only-part 54 --workers 1`. That command omits `--expression-date`; the extractor defaults it to `as_of`. The later self-containment repair retains that source date. This successor explicitly supplies both dates as 2026-06-18.

The [45 CFR 1302 signed manifest](../../.axiom/ingest-manifests/us/regulation/2026-06-24-title-45-part-1302.json) explicitly supplies both dates as 2026-06-22. Its old command also supplies `--allow-incomplete`; its complete 63/63 coverage means that flag changes no artifact. This successor omits it and uses the native command's default completeness requirement. Every date and appendix flag agrees with the predecessor evidence.

## Scope summary

| CFR title-part | Source and expression date | Rows old / new | #832 bodies | Earlier repair bodies | Provision order |
| --- | --- | --- | --- | --- | --- |
| 26-31 | `2026-09-10` | 359 / 359 | 1 | 0 | same |
| 42-407 | `2026-09-10` | 33 / 33 | 1 | 0 | same |
| 42-423 | `2026-09-10` | 360 / 360 | 2 | 0 | same |
| 42-447 | `2026-09-10` | 79 / 79 | 1 | 0 | same |
| 20-404 | `2026-10-08` | 821 / 821 | 10 | 0 | same |
| 47-54 | `2026-06-18` | 272 / 272 | 4 | 16 | inventory order |
| 45-1302 | `2026-06-22` | 63 / 63 | 1 | 1 | same |

Every scope keeps the same citation set, adds zero rows, removes zero rows, keeps parent closure within its scope and places every parent before its children. Every predecessor file matches its lock's hash and size. Every successor path already appears in its predecessor, so these scopes add no citation-path shape or identity to the ratchets.

## 26 CFR part 31

Predecessor: `us/regulation/2026-09-13-title-26-part-31`. Successor: `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31`. Both source and expression date: `2026-09-10`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 26 --only-part 31 --version 2026-09-13-r2026-10-29-ecfr-section-text --as-of 2026-09-10 --expression-date 2026-09-10 --workers 1
```

The row comparison keeps 359 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 1 |
| `/source_path` | 359 |
| `/version` | 359 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/26/31/3121-v-2-1` | 166202 / 166203 | only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

None.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-26-part-31.xml` | `8d5156d440caefafd6586c2f2e4feca124422faf51e50f12da7b3fc1ee0266d0` | `8d5156d440caefafd6586c2f2e4feca124422faf51e50f12da7b3fc1ee0266d0` | yes |
| `ecfr/title-26.structure.json` | `f1fcfb3db9f0cfb00861ce8c81a9da8cab5d3401525ef63a4e48b1d2a1876964` | `f1fcfb3db9f0cfb00861ce8c81a9da8cab5d3401525ef63a4e48b1d2a1876964` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31.json` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31/ecfr/title-26-part-31.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31/ecfr/title-26.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 359/359 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 718 rows, 359 unique paths; 0 additional successor paths; no regression |

## 42 CFR part 407

Predecessor: `us/regulation/2026-09-13-title-42-part-407`. Successor: `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407`. Both source and expression date: `2026-09-10`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 42 --only-part 407 --version 2026-09-13-r2026-10-29-ecfr-section-text --as-of 2026-09-10 --expression-date 2026-09-10 --workers 1
```

The row comparison keeps 33 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 1 |
| `/source_path` | 33 |
| `/version` | 33 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/42/407/25` | 2774 / 2823 | 1 marked caption(s); only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

None.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-42-part-407.xml` | `33fdd29b7af900b96d156779b5e49d05ce7f24985d8dd0e65cfaf5fa02cede75` | `33fdd29b7af900b96d156779b5e49d05ce7f24985d8dd0e65cfaf5fa02cede75` | yes |
| `ecfr/title-42.structure.json` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407.json` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407/ecfr/title-42-part-407.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407/ecfr/title-42.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 33/33 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 66 rows, 33 unique paths; 0 additional successor paths; no regression |

## 42 CFR part 423

Predecessor: `us/regulation/2026-09-13-title-42-part-423`. Successor: `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423`. Both source and expression date: `2026-09-10`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 42 --only-part 423 --version 2026-09-13-r2026-10-29-ecfr-section-text --as-of 2026-09-10 --expression-date 2026-09-10 --workers 1
```

The row comparison keeps 360 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 2 |
| `/source_path` | 360 |
| `/version` | 360 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/42/423/2440` | 1794 / 1882 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/42/423/910` | 5947 / 6041 | 1 marked caption(s); only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

None.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-42-part-423.xml` | `5294e3b1fb9e58c7a779b17fdb2238f250753c86df966f3e86981f1f71e48e47` | `5294e3b1fb9e58c7a779b17fdb2238f250753c86df966f3e86981f1f71e48e47` | yes |
| `ecfr/title-42.structure.json` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423.json` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423/ecfr/title-42-part-423.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423/ecfr/title-42.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 360/360 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 720 rows, 360 unique paths; 0 additional successor paths; no regression |

## 42 CFR part 447

Predecessor: `us/regulation/2026-09-13-title-42-part-447`. Successor: `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447`. Both source and expression date: `2026-09-10`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 42 --only-part 447 --version 2026-09-13-r2026-10-29-ecfr-section-text --as-of 2026-09-10 --expression-date 2026-09-10 --workers 1
```

The row comparison keeps 79 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 1 |
| `/source_path` | 79 |
| `/version` | 79 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/42/447/52` | 4807 / 4810 | only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

None.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-42-part-447.xml` | `01ac3dae19141563320321aac4e4fcfd4afa05760870dd154875aec3eb1546aa` | `01ac3dae19141563320321aac4e4fcfd4afa05760870dd154875aec3eb1546aa` | yes |
| `ecfr/title-42.structure.json` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | `e26fcf6a5b5d463b8402883ca8159ecfdbdc37f3c215fdfaef9efce4d0faf1ed` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447.json` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447/ecfr/title-42-part-447.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447/ecfr/title-42.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 79/79 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 158 rows, 79 unique paths; 0 additional successor paths; no regression |

## 20 CFR part 404

Predecessor: `us/regulation/2026-10-12-with-appendices-title-20-part-404`. Successor: `us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404`. Both source and expression date: `2026-10-08`. Appendix ingestion: enabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 20 --only-part 404 --version 2026-10-12-with-appendices-r2026-10-29-ecfr-section-text --as-of 2026-10-08 --expression-date 2026-10-08 --include-appendices --workers 1
```

The row comparison keeps 821 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 10 |
| `/source_path` | 821 |
| `/version` | 821 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/20/404/1574` | 15666 / 15693 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/1584` | 3437 / 3463 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/1592` | 6826 / 6914 | 2 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/313` | 7319 / 7320 | only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-C/appendix-ii` | 1611 / 1628 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-C/appendix-iii` | 19754 / 19788 | 2 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-C/appendix-iv` | 1342 / 1359 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-C/appendix-v` | 7193 / 7414 | 13 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-P/appendix-1` | 964018 / 964426 | 24 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/20/404/subpart-P/appendix-2` | 30031 / 30082 | 3 marked caption(s); only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

None.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/graphics/ER20NO06.000.png` | `2a0dbb401698a8ef0c36588f828e5994b63f2a514ccb44f8695cb27f0a95c7dc` | `2a0dbb401698a8ef0c36588f828e5994b63f2a514ccb44f8695cb27f0a95c7dc` | yes |
| `ecfr/graphics/ER28MR13.002.png` | `e3ed17f1b437559f8ea932c2a9162fc77dc3bda0e66587a2bc6adaf60db81252` | `e3ed17f1b437559f8ea932c2a9162fc77dc3bda0e66587a2bc6adaf60db81252` | yes |
| `ecfr/graphics/ER28MR13.003.png` | `d193409f45932c41133ce782d07694253ffce4a5e60444710adaac01485ca7c3` | `d193409f45932c41133ce782d07694253ffce4a5e60444710adaac01485ca7c3` | yes |
| `ecfr/title-20-part-404.xml` | `bdf2ce217abc258f999d54f6df1e2c7f6fa7d22ff10b8d0a3b3fc5b086b2fc50` | `bdf2ce217abc258f999d54f6df1e2c7f6fa7d22ff10b8d0a3b3fc5b086b2fc50` | yes |
| `ecfr/title-20.structure.json` | `912fc4243129815b9a1d639fcde6885163a8c43f1d7ae8ce5d186e0e41f5d6cc` | `912fc4243129815b9a1d639fcde6885163a8c43f1d7ae8ce5d186e0e41f5d6cc` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404.json` | equal | Exact bytes |
| `sources/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404/ecfr/graphics/ER20NO06.000.png` | equal | Exact bytes |
| `sources/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404/ecfr/graphics/ER28MR13.002.png` | equal | Exact bytes |
| `sources/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404/ecfr/graphics/ER28MR13.003.png` | equal | Exact bytes |
| `sources/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404/ecfr/title-20-part-404.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404/ecfr/title-20.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 821/821 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 1642 rows, 821 unique paths; 0 additional successor paths; no regression |

## 47 CFR part 54

Predecessor: `us/regulation/2026-06-18-title-47-part-54-r2026-07-15-self-contained`. Successor: `us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54`. Both source and expression date: `2026-06-18`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 47 --only-part 54 --version 2026-06-18-r2026-10-29-ecfr-section-text --as-of 2026-06-18 --expression-date 2026-06-18 --workers 1
```

The row comparison keeps 272 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 20 |
| `/source_path` | 272 |
| `/version` | 272 |

The predecessor's provisions and inventory follow the self-containment repair's global `(level, ordinal, citation_path)` sort. The native successor follows its inventory order, which places each subpart's sections after that subpart. The checker confirms both order origins, keeps all parents before children and records 267 provision positions that differ. The native inventory drops the repair envelope's `document_class`, `jurisdiction`, `source_count` and `version` keys; its `items` retain the same citation set. All 272 inventory rows change `source_path` and update `sha256` to the newly captured part XML hash. These inventory changes follow native extraction.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/47/54/1708` | 3841 / 3887 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/47/54/2007` | 5176 / 5219 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/47/54/505` | 7559 / 7602 | 1 marked caption(s); only captions, caption markers and whitespace change |
| `us/regulation/47/54/621` | 5642 / 5712 | 1 marked caption(s); only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

| Citation path | Body characters old / new | Earlier repair |
| --- | --- | --- |
| `us/regulation/47/54/1003` | 1346 / 1368 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/1014` | 12135 / 12157 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/1016` | 6926 / 6948 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/1018` | 2834 / 2856 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/1019` | 3067 / 3089 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/1020` | 11712 / 11734 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/303` | 2537 / 2853 | Keeps 5 FP formula/definition blocks |
| `us/regulation/47/54/313` | 28996 / 29019 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/322` | 17428 / 17450 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/423` | 2269 / 2291 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/5` | 8909 / 8926 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/503` | 11304 / 11345 | Keeps 2 HED note heading(s) |
| `us/regulation/47/54/624` | 1053 / 1075 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/626` | 3457 / 3556 | Keeps 3 HED note heading(s) |
| `us/regulation/47/54/715` | 2129 / 2153 | Keeps 1 HED note heading(s) |
| `us/regulation/47/54/806` | 5759 / 5781 | Keeps 1 HED note heading(s) |

Removing exactly those source-backed HED/FP blocks from each successor body restores its predecessor body byte for byte. The four new table attributes do not cause these repairs.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-47-part-54.xml` | `0488174308a602b5010528a48c7648b198243739c6ead70c5029f9dd79c0b6f0` | `c1fe59dd29241bb1f112668db2ac2dd46d97d34f44b7f341822c1a99dde7065c` | no |
| `ecfr/title-47.structure.json` | `e6c3999bbdec24e02df7e09bab699ece07dc8842d1e080f552cb852f6c58f1b1` | `e6c3999bbdec24e02df7e09bab699ece07dc8842d1e080f552cb852f6c58f1b1` | yes |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54.json` | equal | Exact bytes |
| `sources/us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54/ecfr/title-47-part-54.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54/ecfr/title-47.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 272/272 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 544 rows, 272 unique paths; 0 additional successor paths; no regression |

## 45 CFR part 1302

Predecessor: `us/regulation/2026-06-24-title-45-part-1302`. Successor: `us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302`. Both source and expression date: `2026-06-22`. Appendix ingestion: disabled.

```bash
uv run axiom-corpus-ingest extract-ecfr --base data/corpus --only-title 45 --only-part 1302 --version 2026-06-24-r2026-10-29-ecfr-section-text --as-of 2026-06-22 --expression-date 2026-06-22 --workers 1
```

The row comparison keeps 63 citations, adds 0, removes 0 and finds no unexpected field changes. It compares every field recursively by `citation_path`. The following table counts every changed provision field; source paths replace the old scope name with the successor name exactly.

| Provision field | Rows changed |
| --- | --- |
| `/body` | 2 |
| `/metadata/body_status` | 1 |
| `/metadata/kind` | 1 |
| `/metadata/label` | 1 |
| `/metadata/label_description` | 1 |
| `/metadata/parent_citation_path` | 1 |
| `/metadata/received_on` | 1 |
| `/metadata/structure_only` | 1 |
| `/source_path` | 63 |
| `/version` | 63 |

The successor keeps provision and inventory order. Inventory rows change only the scope name in `source_path`; coverage changes only `version`.

The filled 1302.1 row drops exactly seven placeholder-only metadata keys: `body_status`, `kind`, `label`, `label_description`, `parent_citation_path`, `received_on` and `structure_only`. All other metadata stays equal. The same retained part XML already contains the direct-child Overview section; the earlier mixed-part traversal repair now reads it.

### The #832 rendering change

| Citation path | Body characters old / new | Source-backed rendering change |
| --- | --- | --- |
| `us/regulation/45/1302/21` | 6315 / 6379 | 1 marked caption(s); only captions, caption markers and whitespace change |

The checker matches each marked caption to the direct `CAPTION` children of its source `TABLE` in its own XML section or appendix and confirms that removing captions and whitespace leaves the same non-caption characters. The zero-caption rows differ only in word separation.

### Earlier extractor repairs this successor also carries

| Citation path | Body characters old / new | Earlier repair |
| --- | --- | --- |
| `us/regulation/45/1302/1` | 0 / 1000 | Fills the structure-only Overview placeholder from existing XML |

The filled body equals the source section's paragraph text. Whole-title structure drift does not touch part 1302 and does not cause this repair.

### Source hashes against the predecessor lock

| Source file inside the scope | Predecessor lock SHA-256 | Successor SHA-256 | Equal |
| --- | --- | --- | --- |
| `ecfr/title-45-part-1302.xml` | `1dc1b061cbb4b7ebb342b374ad58fdf6c66f118a39299b0e08b3bdb0e225e4b2` | `1dc1b061cbb4b7ebb342b374ad58fdf6c66f118a39299b0e08b3bdb0e225e4b2` | yes |
| `ecfr/title-45.structure.json` | `c4462f51bf9f9dee4c9c846b12b38fd5e669d70c8e25b812415335928bf50ac4` | `3b6ccd2bc81643d93f2e7dc7656af87413a8771b3c6d2014f03c0001d56fc21b` | no |

### Reproducibility against the retained research extraction

| Artifact | Byte comparison | Explanation |
| --- | --- | --- |
| `provisions/us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302.jsonl` | equal | Exact bytes |
| `inventory/us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302.json` | equal | Exact bytes |
| `coverage/us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302.json` | equal | Exact bytes |
| `sources/us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302/ecfr/title-45-part-1302.xml` | equal | Exact bytes |
| `sources/us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302/ecfr/title-45.structure.json` | equal | Exact bytes |

### Scope gates

| Gate | Result |
| --- | --- |
| Native coverage | complete, 63/63 |
| Content scan before signing (`scan_scope`, `compare_content_baseline`) | 0 findings; 0 baseline differences |
| Deep release validation | ok=true, 0 errors, 0 warnings |
| Parent closure and order | 0 missing parents; 0 parents after children |
| Scoped citation grammar | 126 rows, 63 unique paths; 0 additional successor paths; no regression |

## Independent source-drift checks

The 47 CFR 54 whole-title structure bytes match. Its part XML differs only in these four added `data-point-width` table attributes; removing exactly those attributes restores the predecessor XML byte for byte:

| Section | Added attribute value |
| --- | --- |
| 54.505 | 330 |
| 54.621 | 300 |
| 54.1708 | 250 |
| 54.2007 | 250 |

The 45 CFR 1302 part XML matches byte for byte. Its whole-title structure contains 23 semantic field differences. The checker finds exactly one part-1302 subtree on each side and confirms their equality. The changes concern part 1336 and its ancestor `size`/`volumes` metadata: sections 1336.30, .31, .32, .33 and .51 change receipt metadata, size and volume. They change no selected part-1302 field.

| JSON pointer | Predecessor value | Successor value |
| --- | --- | --- |
| `/children/1/children/11/children/3/children/0/children/2/children/0/received_on` | `2017-01-05T00:00:00-0500` | `2026-06-25T17:10:14-0400` |
| `/children/1/children/11/children/3/children/0/children/2/children/0/size` | `613` | `724` |
| `/children/1/children/11/children/3/children/0/children/2/children/0/volumes/0` | `4` | `5` |
| `/children/1/children/11/children/3/children/0/children/2/children/1/received_on` | `2017-01-05T00:00:00-0500` | `2026-06-25T17:10:14-0400` |
| `/children/1/children/11/children/3/children/0/children/2/children/1/size` | `1510` | `1621` |
| `/children/1/children/11/children/3/children/0/children/2/children/1/volumes/0` | `4` | `5` |
| `/children/1/children/11/children/3/children/0/children/2/children/2/received_on` | `2017-01-05T00:00:00-0500` | `2026-06-25T17:10:14-0400` |
| `/children/1/children/11/children/3/children/0/children/2/children/2/size` | `648` | `759` |
| `/children/1/children/11/children/3/children/0/children/2/children/2/volumes/0` | `4` | `5` |
| `/children/1/children/11/children/3/children/0/children/2/children/3/received_on` | `2017-01-05T00:00:00-0500` | `2026-06-25T17:10:14-0400` |
| `/children/1/children/11/children/3/children/0/children/2/children/3/size` | `6979` | `7090` |
| `/children/1/children/11/children/3/children/0/children/2/children/3/volumes/0` | `4` | `5` |
| `/children/1/children/11/children/3/children/0/children/2/size` | `14031` | `14475` |
| `/children/1/children/11/children/3/children/0/children/2/volumes` | `['4']` | `[]` |
| `/children/1/children/11/children/3/children/0/children/4/children/1/received_on` | `2017-01-05T00:00:00-0500` | `2026-06-25T17:10:14-0400` |
| `/children/1/children/11/children/3/children/0/children/4/children/1/size` | `541` | `652` |
| `/children/1/children/11/children/3/children/0/children/4/children/1/volumes/0` | `4` | `5` |
| `/children/1/children/11/children/3/children/0/children/4/size` | `9854` | `9965` |
| `/children/1/children/11/children/3/children/0/size` | `59273` | `59828` |
| `/children/1/children/11/children/3/size` | `59273` | `59828` |
| `/children/1/children/11/size` | `1583063` | `1583618` |
| `/children/1/size` | `8122186` | `8122741` |
| `/size` | `14654434` | `14654989` |

## Validation mechanisms and limits

A row-level checker compares each successor with its predecessor by `citation_path`, field by field. It matches each marked caption to the direct `CAPTION` children of its source `TABLE` and confirms that removing captions and whitespace leaves the same non-caption characters. For 47 CFR 54 and 45 CFR 1302 it also confirms that removing the source-backed HED and FP blocks, or the filled Overview body, restores each predecessor body byte for byte. The first 42 CFR 407 comparison looked for `TTITLE` instead of `CAPTION`; the corrected comparison passes and changes no corpus artifact.

Deep validation uses a one-scope selector with `quality_profile: complete-expression-dates-v1` for each successor. `validate-release` checks all four artifact classes, inventory and source hashes, canonical source paths, provision fields, dates, parent closure, citation uniqueness, persisted and recomputed coverage, and content policy. The parent audit (`scripts/audit_release_scope_self_containment.py`) finds no residual parent for any successor.

The repository content scan (`scan_scope` with `compare_content_baseline`) finds zero findings in every successor before signing. `compare_content_baseline` requires every locked scope that the baseline does not list to scan clean, so these scopes need no baseline entry. The positional `content-check` CLI discovers scopes from corpus locks; the post-signing section below records its result.

The citation grammar scan of each predecessor and successor together finds no regression, and direct citation-set equality shows zero new paths across all seven successors. These scopes change no citation ratchet. CI's complete locked-provisions scan remains the authoritative grammar check.

This run changes no citation ratchet, content baseline, reviewed-empty registry, withdrawn-scope registry, release selector or extractor source. The checks compare new extraction against predecessor locks and an independent research extraction of the same commands. They do not certify legal interpretation or transcribe source images.

## Repository checks

| Check | Exit | Result |
| --- | --- | --- |
| `uv run --extra dev ruff check .` | 0 | All checks passed |
| `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports` | 0 | No issues in 106 source files |
| `uv run --extra dev towncrier build --draft --version 0.0.0` | 0 | Draft includes the new fragment once |
| Focused eCFR, anchor and CLI tests (`AXIOM_CORPUS_PARTIAL_TESTS=1`, two workers) | 1 | 413 passed; 10 failed and 26 setup errors |

All 36 unsuccessful focused cases need one of five corpus fixtures that this partial checkout does not fetch: `us-ma/regulation/2026-05-28-365-180-children`, `us/regulation/2026-05-10-snap-7-cfr-273-r2026-07-15-self-contained`, `us/regulation/2026-07-24-1401-coordination-repair-title-26-part-1`, `us/statute/2026-07-24-1401-coordination-repair-title-26` and the `us/regulation/2026-07-23-title-20-part-416` title structure. CI fetches the full corpus and runs the complete suite.

## Extraction commands

Each extraction fetched its locked predecessor first (`uv run axiom-corpus-ingest corpus fetch us/regulation/<predecessor> --workers 1`; every fetch verified all locked files with zero failures), then ran the native command shown in that scope's section. Every extraction exits 0 with complete coverage and zero title errors. The environment uses GIL CPython 3.14.

| Successor | Rows | Coverage |
| --- | --- | --- |
| `2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31` | 359 | complete |
| `2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407` | 33 | complete |
| `2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423` | 360 | complete |
| `2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447` | 79 | complete |
| `2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404` | 821 | complete |
| `2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54` | 272 | complete |
| `2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302` | 63 | complete |

## Release handoff

A separate selector PR replaces each predecessor with its successor. A selector picks one scope from each pair, never both: every pair carries the same citation paths, so selecting both duplicates release citations. That PR validates its complete selector.

| Remove from the new selector | Add to the new selector |
| --- | --- |
| `us/regulation/2026-09-13-title-26-part-31` | `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-26-part-31` |
| `us/regulation/2026-09-13-title-42-part-407` | `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-407` |
| `us/regulation/2026-09-13-title-42-part-423` | `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-423` |
| `us/regulation/2026-09-13-title-42-part-447` | `us/regulation/2026-09-13-r2026-10-29-ecfr-section-text-title-42-part-447` |
| `us/regulation/2026-10-12-with-appendices-title-20-part-404` | `us/regulation/2026-10-12-with-appendices-r2026-10-29-ecfr-section-text-title-20-part-404` |
| `us/regulation/2026-06-18-title-47-part-54-r2026-07-15-self-contained` | `us/regulation/2026-06-18-r2026-10-29-ecfr-section-text-title-47-part-54` |
| `us/regulation/2026-06-24-title-45-part-1302` | `us/regulation/2026-06-24-r2026-10-29-ecfr-section-text-title-45-part-1302` |

Publication, activation and downstream re-pinning stay separate release steps.
