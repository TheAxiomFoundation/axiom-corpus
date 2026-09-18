# Kindergeld proportional adjustment explanation

The official Bundestag memorandum explains that the percentage increase uses the combined child subsistence and care/education allowances. It also distinguishes rounding this legislative adjustment from paying the fixed monthly amount stated in EStG §66(1). This resolves the interpretation needed to reconcile §66(3) with DA-KG V23.1; this source does not enact a rule, amount or commencement.

The existing PDF extractor retains the title page and printed/PDF page 64 from the unchanged 110-page official PDF. Page64 was visually checked against the original image, including the 9,600→9,756 and 255→259 example. The original PDF is retained in full. Native extraction produces one document container and one body. No manual body edits or new extractor code. The adjacent page 64 text includes explanations outside Kindergeld; no completeness or non-bearing claim is made about the omitted draft provisions.

Replay: copy the committed manifest to an untracked file and add local_path pointing to the retained official PDF, then run:

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-09-de-kindergeld-allowance-explanation --manifest /absolute/path/to/replay.json --source-as-of 2026-09-09 --expression-date 2024-09-09
```

The additive immutable selector preserves all 22 previous scopes. Final enacted amounts and dates remain bound to BGBl. 2024 I Nr. 449 and EStG §§32/66. No certification claim.
