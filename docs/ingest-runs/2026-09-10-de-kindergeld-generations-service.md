# All-generations service and paper-signature paragraphs

Native anchored HTML extraction captures the complete SGB VII §2(1a) and
BGB §126(1)–(2) paragraphs from Gesetze im Internet. Three retained official
HTML snapshots produce six rows (three document roots and three content rows).
The source hashes match the recovery probes, and each complete paragraph
matches the already-pinned full-section body after whitespace normalization.
No legal body or generated row was manually edited. The selectors stop at the
next paragraph and retain all four SGB VII sentences and both BGB §126(2)
sentences. The unchanged full parent provisions remain available.

SGB VII §2(1a) defines the service conditions, provider requirements and records
duties. The full captured BFH III R68/11 decision was read separately; its
paragraph22 applies BGB §126(1)–(2) to the statutory service agreement, and
paragraph23 requires specified contractual contents. The consumer review binds
the full judgment. These captures support source-unit-specific native modules;
they do not establish overall written-form validity, provider suitability,
Kindergeld qualification or coverage of the remaining parent paragraphs.
Current writing substitutes and historical applicability remain separate.
Capture date is not statutory commencement. No certified claim.

Reproduce with the native adapter:

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-10-de-kindergeld-generations-service --manifest manifests/de-kindergeld-generations-service.yaml
```

The additive release preserves the 48 prior scopes and adds this scope,
for 49 scopes and 9,882 rows. Publication is separate from serving activation.
