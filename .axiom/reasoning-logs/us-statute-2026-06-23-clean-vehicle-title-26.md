US clean vehicle credit Title 26 corpus ingest reasoning

Impact basis:
- Active/current-law PolicyEngine parity queue identified clean vehicle credits as a national P1 surface with PolicyEngine status `complete`.
- This replaced the prior ACP lane because ACP is sunset and should not be prioritized over active law.

Official source:
- US Code Title 26 USLM XML from uscode.house.gov current releasepoint Public Law 119-99.
- Download URL: https://uscode.house.gov/download/releasepoints/us/pl/119/99/xml_usc26@119-99.zip
- The House download page states this releasepoint is current through Public Law 119-99 dated 2026-06-12.

Scope:
- Ingested only the active clean vehicle credit sections needed for PolicyEngine parity instead of full Title 26.
- Sections included: 26 U.S.C. 25E and 26 U.S.C. 30D.
- This covers the previously-owned clean vehicle credit and new clean vehicle credit surfaces PolicyEngine exposes as `used_clean_vehicle_credit` and `new_clean_vehicle_credit`.

Generated artifact:
- Command used the US Code ingester with repeated `--section` filters; no corpus rows were written by hand.
- Because full Title 26 USLM XML is larger than the scoped review need, the ingester wrote a generated scoped USLM source artifact containing only the selected sections while retaining the official download URL in inventory metadata.
- Output run id: 2026-06-23-clean-vehicle-title-26-title-26.
- Coverage result: complete; 62 source inventory rows matched 62 provision rows.
