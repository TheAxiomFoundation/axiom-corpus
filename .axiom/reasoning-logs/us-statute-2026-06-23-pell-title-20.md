US Pell Grant Title 20 corpus ingest reasoning

Impact basis:
- The active PolicyEngine parity queue identifies `pell_grant` as a national P1 surface with PolicyEngine status `complete`.
- Pell is active current law for the 2026-27 award year, unlike expired ACP work, so it is appropriate to prioritize before historical/sunset programs.

Official source:
- US Code Title 20 USLM XML from uscode.house.gov current releasepoint Public Law 119-99.
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/99/xml_usc20@119-99.zip
- The same House releasepoint family was used for current-law clean vehicle ingestion and is current through Public Law 119-99 dated 2026-06-12.

Scope:
- Ingested only 20 U.S.C. 1070a, the Federal Pell Grants section, instead of full Title 20.
- This section defines the Pell Grant amount paths, maximum/minimum Pell criteria, SAI-calculated Pell amount, less-than-full-time adjustment, cost-of-attendance cap, special rule, eligibility period, application and appropriation provisions.

Generated artifact:
- Command used the US Code ingester with a `--section 1070a` filter; no corpus rows were written by hand.
- The ingester wrote a generated scoped USLM source artifact while preserving the official House download URL in inventory metadata.
- Output run id: 2026-06-23-pell-title-20-title-20.
- Coverage result: complete; 41 source inventory rows matched 41 provision rows.
