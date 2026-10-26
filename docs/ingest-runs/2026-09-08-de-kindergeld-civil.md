# Kindergeld civil-law and judgment capture tranche

This additive capture addresses dependencies exposed during signed encoding.
It does not assert dependency closure or authorize a certified claim.
The new selector preserves all fourteen scopes of the published
`de-rulespec-2026-09-08-kindergeld-frontier` release, adding two scopes with
3,138 rows through existing adapters, without modifying adapter code.

Commands:

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-de-gii --base data/corpus --version 2026-09-08-de-kindergeld-civil-dependencies --manifest manifests/de-kindergeld-civil-dependencies-gii.yaml --source-as-of 2026-09-08
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-cjeu --manifest manifests/de-kindergeld-cjeu-c-411-20.yaml
```

The GII scope contains the full current BGB and Unification Treaty (3,136
rows). Relevant recovered paths include `de/statute/bgb/2`, `/187`, `/188`,
`/1589` and `de/statute/einigvtr/art-3`. Article 3 names Brandenburg,
Mecklenburg-Vorpommern, Sachsen, Sachsen-Anhalt, Thüringen, and only the part
of Berlin where the Grundgesetz previously did not apply. It does not permit
a rule treating all of Berlin as the historical accession territory. BGB
§187(2) expressly covers age calculation, and §188 addresses calendar periods
and a missing corresponding day in the final month. These sources must be
encoded before replacing legal age or calendar-duration conditions with
computed rules. This current capture alone does not prove 2025 applicability
of every provision in either act; no backdated expression date is asserted.

The judgment scope retains the full 17-page German judgment of 1 August 2022,
C-411/20, ECLI:EU:C:2022:602, including paragraphs 1–74 and the operative part.
The URL was resolved through the official Publications Office work,
German-expression and PDF-manifestation RDF graph, not a secondary summary.
The supported `guidance` storage namespace is used with explicit
`document_type: court judgment`; this does not reclassify the court as an
administrative agency. The operative part concerns unequal treatment during
the first three months and the inapplicability of Article 24(2) of Directive
2004/38 to that rule. Paragraphs 70–72 retain the habitual-residence condition
and case-specific factual assessment. This capture therefore does not support
an unconditional award to every new arrival or resolve residence judgments.

Coverage reports show zero missing and zero extra rows in both scopes.
The companion audit records provision-file hashes and each row/body hash.
Existing scope bytes remain unchanged. Neither capture claims exhaustive
BMF/BZSt/court discovery. Eight BMF handbook pages, historical applicability,
and signed substantive dependency encodings remain open. The isolated
headless attempt to retrieve AEAO §9 timed out and no response was accepted
as corpus text; the parallel US browser and checkout were not modified.
