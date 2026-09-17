# Bounded primary-source parentage context

The immutable parentage release already retains the complete original KindRG
PDF and its 26-page OCR body. The encoder limits amendment-body context to
12,000 characters; the full body has 121,357 characters and the commencement
clause is on its final page. This additive scope extracts only PDF pages 1
and 26 (printed pages 2942 and 2967), using the existing `page_windows`
configuration. The resulting 7,339-character body contains both the BGB §1591
sentence and Article 17 §1 commencement. It is a disclosed excerpt, not a
replacement or a claim to have captured the complete act in these two pages.
The original full-act scope is preserved unchanged.

The source PDF is byte-identical to the official archive capture, SHA-256
`bd58391268f7d4103670967f86ab7642fe9bae34faf56ec36415b2dadc1e2c7b`.
The original pages were visually verified; both operative sentences remain
exact substrings of the excerpt. Existing German Tesseract 5.5.3 extraction
and the same language model supply OCR, with no manual body changes. Other
OCR text remains subject to visual verification before use in proof atoms.

Replay uses an untracked copy of the committed manifest with `local_path`
set to the absolute retained original PDF, as documented for the preceding
parentage-history capture:

```sh
TESSDATA_PREFIX=/path/to/deu-model-directory PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-parentage-context --manifest /absolute/path/to/replay-manifest.json --source-as-of 2026-09-08 --expression-date 1997-12-16
```

This capture adds two rows and preserves all nineteen prior release scopes.
The separate encoder amendment-discovery fix must be reviewed and pinned;
this excerpt does not bypass context selection, signing, legal review or
source completeness. RuleSpec #48 remains unmerged for temporal and other
review findings. No serving activation or certification claim.
