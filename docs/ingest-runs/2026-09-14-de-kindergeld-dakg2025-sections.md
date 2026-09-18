# DA-KG 2025 numbered-section capture

The native labeled-PDF adapter now captures all 420 numbered O, A, V, R and S
sections on pages 13–159 of the retained original DA-KG Stand 2025. The label set
matches the existing axiom-oracles heading census exactly. The complete
173-page PDF is retained; preface, contents and appendix pages are not normalized
by this scope. This is source capture, not a disposition or encoding of 420 rules.

The source is BZSt-authored material downloaded from the Tacheles mirror.
Its exact SHA-256, 33e1a8c4f6bd65034febc9d0c45850e64e982f665f519f08eaeceb80ac02dedd,
is already bound by the ledger's de-subject-003 receipt. The live official legacy
URL now returns the different 2026 edition. Authorship and transport are explicitly
distinguished; neither a current government-host 2025 download nor BZSt
cryptographic authentication of the mirror is claimed. The expression date records
the capture date, not inferred issuance or commencement.

Extraction uses existing native options only. Bold section labels identify the
420 boundaries. Section labels are mapped to lowercase hyphenated citation suffixes.
Wrapped heading continuation is restricted to exact title lines observed in this
PDF and checked against the retained official contents census. A broad continuation
pattern was rejected because it absorbed unnumbered operative paragraphs; the
style-only default also absorbed O 4.5's first paragraph. The final manifest uses
only exact source-observed title lines and preserves every resulting body span.

The companion audit compares all 420 source body spans with the native rows after
whitespace normalization. Seventy-eight structural or repealed-heading rows have
empty bodies; their headings remain in the records. Source page numbers and
intervening chapter labels are retained rather than silently removed. These
non-operative artifacts must not be interpreted as legal thresholds or rules.
The section heading is separate from the body, as in the native labeled adapter.

The `numbered-sections` namespace avoids colliding with the previously captured
A 19.2 document root and its document-1 child. Both represent the same source
section; future consumers must choose a canonical executable module and bind
restatement provenance, rather than encode the same legal rule twice.

Reproduce with manifests/de-kindergeld-dakg2025-sections.yaml and a temporary
runtime copy whose local_path points at the retained source snapshot:

```bash
axiom-corpus-ingest extract-official-documents --base data/corpus \
  --version 2026-09-14-de-kindergeld-dakg2025-sections \
  --manifest /path/to/runtime-manifest.json
```

The cumulative release preserves all 57 prior DE scopes and adds this one scope.
No generated corpus row, inventory, coverage report or PDF was manually edited.
The ledger remains open until bearing provisions are encoded and bound.
