# Source Discovery Checklist

This checklist tracks external discovery inputs that can help find primary
policy sources without becoming corpus sources themselves.

The corpus contract remains source-first: ingestion snapshots primary official
documents, builds inventories from those documents, extracts normalized
provisions, and publishes corpus artifacts from that source tree. External
models, datasets, reports, and citation lists are only gap-finding aids.

## PolicyEngine References

PolicyEngine-US and PolicyEngine-UK contain thousands of claim-level references
to statutes, regulations, agency manuals, tax forms, tables, and guidance
documents. These references are useful for discovering public policy source
documents, but they must not become a runtime dependency or privileged upstream
for Axiom.

Use this as an offline checklist only:

- [x] Export static URL inventories from PolicyEngine-US and PolicyEngine-UK into
      review artifacts.
- [ ] Preserve the citing parameter or variable path in the generated inventory.
- [x] Normalize URL variants, strip page anchors into separate metadata, and
      deduplicate by canonical URL.
- [x] Classify each URL by source status: primary official, official-but-not-
      current, secondary mirror, analytical report, vendor-only, or unknown.
- [x] Classify each primary official URL by document class: statute,
      regulation, manual, state plan, waiver, agency memo, tax form
      instruction, data table, or other policy document.
- [ ] Prioritize official/open URLs that are not already covered by current
      release artifacts.
- [x] Seed a fillable coverage manifest from ready official source groups:
      `manifests/policyengine-source-coverage.yaml`.
- [ ] For each selected URL or source group, create or extend a corpus manifest that points to
      the official source directly. Do not ingest from PolicyEngine files.
- [ ] Preserve the external citation path only as discovery provenance, such as
      `discovered_via: policyengine-us:<parameter-or-variable-path>`, not as a
      legal source.
- [ ] Exclude LexisNexis, Westlaw, Cornell, Justia, Casetext, public.law, and
      similar mirrors from automatic ingestion unless a jurisdiction confirms
      that endpoint as the official publisher or we add an explicit secondary
      audit document class.
- [ ] Re-fetch every selected document from the official source during corpus
      ingestion and store it under `sources/{jurisdiction}/{document_class}/...`
      with Axiom-owned hashes and timestamps.
- [ ] After ingestion, validate that the PE-cited policy point is traceable to
      an Axiom source/provision, then mark that discovery item covered.

Do not:

- import PolicyEngine packages from the corpus pipeline
- read PolicyEngine YAML during production ingestion
- treat PolicyEngine parameter values as source text
- let a PE citation substitute for official source discovery or coverage

Useful current scale from fresh upstream PolicyEngine-US and PolicyEngine-UK
clones:

- 9,830 raw URL references across `.yaml`, `.yml`, `.py`, and `.md` files
- 7,197 canonical URLs after normalization
- 1,437 official/open URLs ready for manifest review
- 158 fillable source groups in `manifests/policyengine-source-coverage.yaml`
- 5,050 URLs needing review and 710 blocked/excluded URLs retained in the JSON report

Those counts are discovery scope, not corpus coverage.

The current ops artifact is
`data/corpus/analytics/source-discovery-current.json`, generated from the
static URL lists under `sources/policyengine-us/`. It powers the Axiom `/ops`
Source Discovery Backlog section and should be refreshed when the offline
inventory changes.

The broader PolicyEngine coverage seed can be regenerated as
`data/corpus/analytics/source-discovery-policyengine-current.json` from:

- `sources/policyengine-us/all_url_references.txt`
- `sources/policyengine-uk/all_url_references.txt`

Its `group_rows` are materialized into
`manifests/policyengine-source-coverage.yaml`. Fill that manifest in first,
then promote reviewed groups into source-first ingestion manifests.

The current seed is URL-based. Non-URL legal citations in PolicyEngine, such as
bare Act, Code, or regulation references without `href` values, need a second
extraction pass and should be added to `additional_source_sets` or merged into
existing document groups.

Federal Register URLs in the discovery report should be promoted through the
`extract-federal-register` adapter, not through the generic official-document
path. That keeps the activity feed as `document_class=rulemaking` with agency,
docket, RIN, CFR-reference, comment-deadline, and effective-date metadata
instead of flattening each notice into an isolated policy document.

For agent assignment, prefer `ready_for_manifest` rows whose source status is
`primary_official`. Do not assign vendor-only or source-access-blocked items to
ingestion agents until there is an explicit official export, license, or access
path to use.

Use `group_rows` in the report before assigning work from raw `rows`.
`group_rows` collapses uncovered `ready_for_manifest` URLs into actionable
manifest candidates by jurisdiction, document class, and source family. This is
especially important for forms, where the raw inventory often contains multiple
yearly tax booklet, schedule, and instruction URLs that should be scoped as a
coherent current-year manifest before historical years are added.
