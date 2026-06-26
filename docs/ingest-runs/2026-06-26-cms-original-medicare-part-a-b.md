US CMS Original Medicare Part A and B corpus ingest reasoning

Impact basis:
- PolicyEngine parity encoding for Medicare needs a public source that states
  the simplified Medicare eligibility surface used by PolicyEngine's
  `is_medicare_eligible` variable.
- Existing RuleSpec covers 42 U.S.C. 426 source-level limbs, but the
  PolicyEngine surface combines age-65 and 24-month disability paths as a
  simplified final eligibility proxy.

Official source:
- Centers for Medicare & Medicaid Services, "Original Medicare (Part A and B)
  Eligibility and Enrollment."
- URL: https://www.cms.gov/medicare/enrollment-renewal/original-part-a-b
- CMS page metadata and page content identify the source as a CMS Medicare
  enrollment and renewal page.

Scope:
- Ingested the CMS HTML page as federal guidance under
  `us/guidance/cms/original-medicare-part-a-b`.
- The generated blocks include CMS statements that Medicare Part A and Part B
  are available to people age 65 or older, disabled people, and people with
  ESRD; that premium-free Part A based on age requires age 65 or older; that
  disability-based Part A entitlement follows 24 months of Social Security or
  Railroad Retirement Board disability benefits; and that disabled individuals
  are automatically enrolled in Medicare Part A and Part B after 24 months of
  Social Security disability benefits.

Generated artifact:
- Command used the generic official-document extractor; no corpus rows were
  written by hand.
- Output run id: 2026-03-10-cms-original-medicare-part-a-b.
- Coverage result: complete; 31 source inventory rows matched 31 provision
  rows.
