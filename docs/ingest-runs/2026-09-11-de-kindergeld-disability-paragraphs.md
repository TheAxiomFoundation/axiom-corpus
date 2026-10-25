# Complete disability-definition paragraph units

The native official-document adapter selects the first paragraph under
`#tab-content` from each unchanged official DRV section2 page. All sentences
are retained, including threatened disability. The two resulting bodies match
the first paragraphs of the retained whole-section rows after whitespace
normalization. The2001and2018 expression dates and source snapshots remain
separate. No paragraph2/3 severe-disability shortcut is substituted.

```bash
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-11-de-kindergeld-disability-paragraphs --manifest manifests/de-kindergeld-disability-paragraphs.yaml
```

The local run used the native local_path option on the same retained official
HTML snapshots. Four rows and complete coverage are generated. The additive
BGH-counterpart release selector now contains54 scopes,10211 rows and407
artifacts. No legal row, RuleSpec module or encoding manifest was hand-edited.

The initial default HTML blocks failed the A6 grammar gate. The final native
anchor-range configuration uses semantic `inhalt` paths, selecting paragraph1
up to paragraph2. Both legal bodies and their SHA-256 values are unchanged.
The grammar baseline is unchanged.
