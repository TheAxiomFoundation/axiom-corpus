# Remaining Kindergeld handbook capture

This adds the eight previously unavailable BMF pages to the still-unpublished
`de-rulespec-2026-09-08-kindergeld-civil` selector: EStH 2024 §§32, 32b, 33a;
LStH 2023 §§3b, 8, 9; AEAO 2025 §9; and Anhang 45, AStBV (St) 2025.
The existing official-documents adapter captured the complete HTML from each
official edition-specific URL and extracted the main content from `#Inhalt`,
including collapsed R/H/AEAO guidance. No adapter code was changed.

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-handbooks-remaining --manifest manifests/de-kindergeld-bmf-handbooks-remaining.yaml --expression-date 2026-09-08
```

The browser-user-agent attempt failed at the second page's main-content
selector and wrote no accepted scope. A subsequent run using the adapter's
default request succeeded on all eight pages. An unsupported custom-header
configuration present in that successful invocation was ignored by the
adapter and removed from the retained manifest; the retained manifest uses
the same effective default request behavior. No challenge response was
accepted as legal text. The release dry-run rejected the adapter’s default
non-ISO expression date (the scope name). A final full capture with the
explicit ISO expression date above replaced that unpublished attempt; all
sixteen rows now record the actual capture date.

The scope has sixteen rows (eight document parents and eight `inhalt`
children), with complete coverage and zero missing, extra or duplicate
citations. Body lengths range from 4,326 to 221,265 characters. Inspection
confirmed the expected section starts, guidance material and terminal text;
the audit records every row and body hash. The source inventory binds the
eight retained HTML snapshots to the official URLs and response hashes.

This supplements, without changing, the already signed civil-law and judgment
tranche. The selector now contains 7,637 rows across seventeen scopes.
Edition labels remain separate from actual capture expression dates. Source
availability does not establish historical applicability or encode a rule.
The four discovery classes and substantive Kindergeld dependencies remain
open. No serving activation or certified claim is made.
