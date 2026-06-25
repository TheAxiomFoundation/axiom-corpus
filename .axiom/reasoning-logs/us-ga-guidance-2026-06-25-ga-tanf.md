US Georgia TANF guidance corpus ingest reasoning
================================================

Objective
---------

Add the official Georgia DFCS TANF Eligibility Requirements guidance page to support Axiom encoding of Georgia TANF eligibility and resource-limit rules for PolicyEngine parity.

Source selection
----------------

- The source is published by the Georgia Department of Human Services Division of Family and Children Services on the official `dfcs.georgia.gov` domain.
- The page states member eligibility criteria and includes the financial-criteria example that an assistance unit of three must have gross income below $784 per month and countable assets below $1,000.
- Georgia SOS rule pages were checked but direct automated access returned HTTP 403 during this run, so the accessible DFCS official source was ingested rather than relying on PolicyEngine references or hand-written corpus rows.

Extraction
----------

- Command: `uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-06-25-ga-tanf --manifest manifests/us-ga-tanf-guidance.yaml`
- Content selector: `.content-page__main`
- A second scoped document uses `.content-page__main > p:nth-of-type(11)` for the `Income/Resources` paragraph so encoders can target the financial criteria without reprocessing the full eligibility page.
- No normalized corpus rows were edited by hand.

Validation notes
----------------

- The official-document extractor emitted one document row and one block row.
- Coverage reported complete with zero missing and zero extra citations.
