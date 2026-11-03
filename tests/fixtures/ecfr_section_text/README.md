# Live eCFR sections for section-text rendering

Each fixture copies one section (`DIV8`) or appendix (`DIV9`) from the eCFR
Versioner's full title XML for 2026-10-29
(`https://www.ecfr.gov/api/versioner/v1/full/2026-10-29/title-N.xml`). A full
fixture holds the unit's exact source bytes. An excerpt keeps the unit's start
tag, its `HEAD` and the listed elements, each as its exact source bytes, joined by
newlines; it omits the unit's other elements.

Before #942, `_section_body` dropped the text of every element type listed below.
`tests/test_corpus_ecfr_section_elements.py` renders each fixture and checks the
element's text.

| Fixture | Unit | Element types |
| --- | --- | --- |
| `26-cfr-1-661-c-2.xml` | 26 CFR 1.661(c)-2 | `LDRWK`, `FL-2`, `LDRFIG` |
| `37-cfr-2-7.xml` | 37 CFR 2.7 | `LDRWK`, `FL-2`, `LDRFIG` (the whole body) |
| `26-cfr-1-613-2.xml` | 26 CFR 1.613-2 | `SCOL2`, `LI` |
| `10-cfr-110-28.xml` | 10 CFR 110.28 | `SCOL2`, `LI` (the whole body) |
| `26-cfr-1-861-10.xml` | 26 CFR 1.861-10 | `FP1-2` |
| `30-cfr-75-905.xml` | 30 CFR 75.905 | `HD1` |
| `7-cfr-1051-2.xml` | 7 CFR 1051.2 | `HD2` |
| `46-cfr-196-37-47.xml` | 46 CFR 196.37-47 | `HD3` |
| `14-cfr-241-section-18.xml` | 14 CFR part 241, section 18 | `HD5` |
| `43-cfr-3287-4.xml` | 43 CFR 3287.4 | `HED1` |
| `21-cfr-12-45.xml` | 21 CFR 12.45 | `DOCKETHD`, `HD1` |
| `48-cfr-chapter-2-appendix-h.xml` | Appendix H to 48 CFR chapter 2 | `SECHD` |
| `48-cfr-chapter-2-appendix-f-excerpt.xml` | Appendix F to 48 CFR chapter 2 | `PARTHD`, `SECHD` |
| `46-cfr-11-505.xml` | 46 CFR 11.505 | `TCAP` |
| `29-cfr-2530-210-excerpt.xml` | 29 CFR 2530.210 | `TCAP` that starts with a label |
| `46-cfr-42-13-25.xml` | 46 CFR 42.13-25 | `BCAP` |
| `27-cfr-19-661.xml` | 27 CFR 19.661 | `SECAUTH` |
| `38-cfr-21-7614.xml` | 38 CFR 21.7614 | `PARAUTH` |
| `7-cfr-800-166.xml` | 7 CFR 800.166 | `APPRO` |
| `12-cfr-4-92.xml` | 12 CFR 4.92 | `XREF`, which stays out of the body |
| `29-cfr-301-9.xml` | 29 CFR 301.9 | `FRP` |
| `46-cfr-42-50-10.xml` | 46 CFR 42.50-10 | `FRP0` |
| `21-cfr-1210-22.xml` | 21 CFR 1210.22 | `P2`, `P-DASH` |
| `49-cfr-1248-2.xml` | 49 CFR 1248.2 | `P1` |
| `12-cfr-30-appendix-c.xml` | Appendix C to 12 CFR part 30 | `P-1` |
| `33-cfr-116-50.xml` | 33 CFR 116.50 | `P-2`, `FP1-2` |
| `28-cfr-50-14-excerpt.xml` | 28 CFR 50.14 | `P-3`, `HD1` |
| `40-cfr-63-365-excerpt.xml` | 40 CFR 63.365 | `FP2` |
| `16-cfr-436-5-excerpt.xml` | 16 CFR 436.5 | `FP2-2` |
| `49-cfr-179-400-9.xml` | 49 CFR 179.400-9 | `FP2-3` |
| `26-cfr-521-101-excerpt.xml` | 26 CFR 521.101 | `NAME` |

The issue names 26 CFR 1.661(c)-2, 1.613-2 and 1.861-10. The other units are the
smallest live sections or appendices that hold each element type, found by a
census of all 49 titles; an excerpt cuts a unit over 10 KB down to the elements
around the first instance.

Source title XML SHA-256 (2026-10-29):

| Title | SHA-256 |
| --- | --- |
| 7 | `8fd2ffe53f4a9a0fc135fa0b3645438b85f0a0f678d76c1a349d2a0d08b7fcf2` |
| 10 | `c7e3557556804cef758b9fae378471e2f467cdf9332cf71f3756744c875d9e0f` |
| 12 | `3e088dc23255b39e5db788d7b26b3d600bfc2f6632d92939d4a70ebf67657365` |
| 14 | `098120edc1a787a87b17674bd1a0fa38b10fb9938c61c9db8143c807e83d7810` |
| 16 | `cf260ebbd07371fb82404bec064ecc17a731beb3636aa0896f3625038b5e62e7` |
| 21 | `f552ee88a4b85de8e2e799bad2229e3bea0d1de026790b0042247c3ec34f5ccc` |
| 26 | `b0cd2f471232b2281b2a4467c2096e15f6d5c04e54e0441746cdfa0d68bb1483` |
| 27 | `685b8e8636d88221a1633c3f7e76ff129d179aea48e4828e37fb2d54c591ddf8` |
| 28 | `d722dc3fdb1982f011ad254d2584d26be452d9939cdc936263dd8e932fa6e29a` |
| 29 | `c4e77f8c5cd8c746226153b7402d926d078552d271c1de3ad5529a698a1bde55` |
| 30 | `f9bd59286b0fe8b473da6b4788ebf87713286687c64e062a4bf0607ae8338427` |
| 33 | `d47582e1120bf2697f1848063bf3f1367a6cc4504940a4879775d0af8b01cbac` |
| 37 | `8d4322405c67ef841916650e76ec56d50f0f538e7f5a4565608f5fb2b09b6089` |
| 38 | `9506de6c7c4f940355bb13f1aba679208554bb39516ff67ffe9f01079e4654b6` |
| 40 | `e94c1d854454c206c8c37627531701f6ecbabed85a52217118a28ab198eaa236` |
| 43 | `775dc9e126d80779338ae453323399d73e1c93b8bed115c1eb00faca69b575b2` |
| 46 | `495c1da7d1a24ffe6a68d09842c14f49a9119ad57caf3c9686c948e1d51a149f` |
| 48 | `be0cd8f805bfc64af6183d6a5e96310150ba3f3df76ce4c24c7d26f98d961885` |
| 49 | `3fdae9d80739fc9abf63a2fd16119733785df379e44a766b64f63fe8eacfb341` |
