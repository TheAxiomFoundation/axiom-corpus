# Georgia SSP manual corpus ingest reasoning

PolicyEngine-US models `ga_ssp`, `ga_ssp_person`, and `ga_ssp_eligible_person` from Georgia DFCS PAMMS Medicaid manual sections 2578 and 2136.

Section 2578, "SSI Recipients", contains the executable State Supplement eligibility setting for SSI-only recipients entering a nursing home and the effective-date payment amount table: $20 from July 1, 2006; $35 from July 1, 2018; and $40 from July 1, 2019.

Section 2136, "Institutionalized Hospice", defines the institutionalized hospice setting referenced by PolicyEngine's Georgia SSP eligibility input and points SSI-only institutionalized hospice cases back to Section 2578 case management.

Both sources are official Georgia Department of Human Services Division of Family and Children Services PAMMS pages. The official-document ingester is used with `article.doc` so corpus rows are generated from the manual content and not from site navigation or hand-written rows.
