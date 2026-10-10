# Kindergeld BMF letter and country-group context

Retain the official EStH 2024 reprint of the BMF letter dated 28 June 2013, the complete BMF country-group letter dated 2 December 2025 (four pages), and the full German CJEU judgment C-328/20, corrected on 6 September 2022 (29 pages). The country-group PDF pages 1–4 and judgment operative pages 28–29 were visually checked. These captures do not encode the rules or establish BStBl II publication of the judgment.

The 2025 letter replaces the 18 December 2023 table from assessment year 2025. Its EU/EEA footnote explicitly addresses EStG §32(6) sentence 4 and §33a(2) sentence 2; it does not establish a blanket exemption for every provision in the header. The 2013 letter is retained as the edition-specific handbook restatement, with its capture date separate from its historical application statement. The judgment records both judgment and correction dates.

No extractor changes or manual provision-body edits. Three other attempted handbook captures returned browser challenges and are excluded. The release selector preserves all 23 existing scopes and adds this guidance scope.

Replay: copy the committed manifest to an untracked JSON file, add local_path for each retained source snapshot, and run the native extractor from a clean generator commit:

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-09-de-kindergeld-bmf-letter-context --manifest /absolute/path/to/replay.json --source-as-of 2026-09-09 --expression-date 2026-09-09
```
