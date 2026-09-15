# BFH cross-border recipient-priority originals

The complete review of BFH III R31/15 identifies five earlier judgments in
paragraphs 22–23: III R17/13, III R8/13, III R11/13, III R10/13 and III R14/13.
The native official-document adapter captures their original official BFH PDFs,
retaining all 18 pages as five document roots and five content rows. Independent
review and a local `pdftotext -raw` comparison verify exact conservation after
whitespace normalization. Representative first and final pages were visually
inspected. No generated source text or corpus row was manually edited.

Reproduce the capture with:

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-15-de-kindergeld-cross-border-priority --manifest manifests/de-kindergeld-cross-border-priority.yaml
```

The recorded run used the same manifest with `local_path` entries pointing to
the exact receipted official PDFs. The companion audit binds the runtime
manifest, PDF bytes, normalized bodies and page counts. Decision dates are
expression dates; capture and publication dates are separate.

The new selector preserves all 59 prior scopes and appends this one. These
captures do not establish a complete legal review, current bearing, BStBl II
issue membership or executable coverage. Publication does not activate serving
or announce certification.
