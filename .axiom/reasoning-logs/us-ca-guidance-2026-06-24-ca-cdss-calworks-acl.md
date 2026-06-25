California CalWORKs 2024 CDSS ACL guidance corpus ingest reasoning

Impact basis:
- The active PolicyEngine parity queue identifies California CalWORKs cash assistance as a high-impact active state surface with PolicyEngine status complete and Axiom RuleSpec encoding still pending.
- The current California CalWORKs implementation depends on current CDSS All County Letter guidance for vehicle limits, resource limits, and maximum aid payments.

Official sources:
- ACL 24-36, issued by the California Department of Social Services on May 31, 2024, sets the July 1, 2024 non-exempt vehicle value limit.
- ACL 24-54, issued by the California Department of Social Services on August 2, 2024, sets the July 1, 2024 maximum resource limit.
- ACL 24-55, issued by the California Department of Social Services on August 8, 2024, sets the October 1, 2024 CalWORKs maximum aid payment standards.

Scope:
- Ingested only CalWORKs ACLs from the existing CDSS ACL source discovery set, excluding the adjacent CalFresh ACL 24-59 document.
- Preserved the official PDFs, source inventory, page-level provision records, and coverage report under the `us-ca` guidance scope.

Generated artifact:
- Command used the generic official-document ingester over `manifests/us-ca-cdss-calworks-acl-guidance.yaml`; no corpus rows were written by hand.
- Output run id: 2026-06-24-ca-cdss-calworks-acl.
- Coverage result: complete; 23 source inventory rows matched 23 provision rows across 3 official documents.
