`publish_corpus.py` checks the released scopes a union release reuses in
seconds, not hours: it verifies each prior signed release object once (not
once per scope that object holds) and builds each release content's scope
identities in one pass over its scopes and artifacts. The
`released-scope-lookup` phase took 4 h 26 min in run 38305879426 while its
database reads took 24 s.
