# Historical SGB IV §8(1a) threshold source

The native official-documents extractor selects the complete paragraph (1a), all three sentences, from the retained official Deutsche Rentenversicherung historical HTML. The source bytes are identical to the full-section capture in the preceding release; the manifest records that snapshot hash and the displayed validity interval, 1 March 2024 through 31 December 2025.

The paragraph defines the monthly threshold by reference to the hourly minimum wage, specifies multiplication by 130 and division by three with rounding upward to whole euros, and assigns publication to BMAS. The extracted body was checked against the entire selected HTML paragraph after whitespace normalization. No provision body was edited.

Reproduce with `extract-official-documents --base data/corpus --version 2026-09-09-de-kindergeld-sgbiv8-threshold-paragraph --manifest manifests/de-kindergeld-sgbiv8-threshold-paragraph.yaml`. The recorded capture used the supported `local_path` replay of the exact official snapshot; only transport differs. The full §8 historical row retains every other paragraph. This paragraph capture does not establish employment eligibility or close the full section.

The additive named-release selector retains all 40 prior scopes and adds this one scope (two rows). No serving activation or certification claim is made.
