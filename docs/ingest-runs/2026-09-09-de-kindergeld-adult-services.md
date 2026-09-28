# Kindergeld adult-child service sources

EStG § 32(4) expressly refers to service regimes whose primary texts were absent from the preceding release. This additive cut captures seven complete current acts through the native GII adapter: JFDG, BFDG, EhfG, ZDG, SG, WPflG and SGB VII. It also captures the complete German Regulation (EU) 2021/888 including its annex, the statutory-reference 2016 weltwärts guideline, and the complete IJFD guideline as amended on 4 January 2021 (GMBl 2021, pages 77–80).

Current consolidations are not substitutes for the text applicable in 2025. The official DRV archive supplies SG § 58b effective from 13 April 2013 through 31 December 2025 as a separate version-qualified citation. Its six-month probation plus up to seventeen further months differs from the current six-to-eleven-month rule. Other historical service-period questions remain for source-bound encoding review.

The 2016 weltwärts edition is the reference named in EStG. Later programme revisions are not silently substituted. The IJFD PDF contains the full 16-page official gazette issue; native page windows retain only the complete guideline on PDF pages 13–16. Its temporary Covid provision expressly expires on 31 May 2021 and must not be applied in 2025. The full EU act has 23 pages and weltwärts has 15 pages. All captured PDF text matches the entire selected source-page extraction after whitespace normalization; original source files and source hashes are retained. IJFD beginning/end pages were visually checked for clipping and adjacent-instrument contamination.

The GII capture reports 746 matched rows, zero missing and zero extra. Official PDF captures report two regulation rows and four guidance rows. The archived SG row is captured separately. Existing release scopes and historical SGB allowance texts remain byte-identical.

## Reproduction

Run native `extract-de-gii` with `manifests/de-kindergeld-adult-services-gii.yaml`, version `2026-09-09-de-kindergeld-adult-services` and source-as-of `2026-09-09`. Run `extract-official-documents` separately for the regulation and guidance manifests using that same version. The historical SG manifest uses version `2026-09-09-de-kindergeld-adult-service-history`.

The ministry PDF connection was reset twice for the native HTTP client. The same official URL succeeded with curl; the retained-byte replay uses the supported `local_path` manifest field and verifies the declared snapshot SHA before native extraction. To reproduce offline, copy each committed manifest to an untracked JSON file and add `local_path` pointing to its retained official source artifact. This changes transport only: segmentation, corpus rows, coverage and signatures are produced by the native pipeline. Sign each scope from a clean committed generator tree. No adapter implementation was changed.

The named release is a publication plan, not serving activation. These captures do not establish complete Kindergeld entitlement or certification.
