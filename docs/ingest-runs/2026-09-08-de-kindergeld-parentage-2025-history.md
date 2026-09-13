# Archived parentage provisions for the 2025 Kindergeld composition

The current consolidated BGB capture includes parentage amendments effective
in 2026. The 2025 consumer therefore needs dated historical evidence before
recognition and challenge rules can be encoded. This tranche captures nine
archived statutory sections from the official Deutsche Rentenversicherung
rvRecht normative archive: §§1594–1599, 1600, 1600a and 1600b. Each archive
page explicitly supplies an effective date and validity through 31 March 2026.

The existing official-document CLI preserves nine HTML snapshots and creates
18 rows (nine document roots and nine content bodies), with inventory and
complete coverage. Version-qualified citation paths keep current consolidated
rows separate. For example, historical §1595(2) conditions the child's consent
on the mother not having parental custody in that respect; the current row
has a different condition. No source body is manually rewritten.

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-parentage-2025-history --manifest manifests/de-kindergeld-parentage-2025-history.yaml
```

The adjacent audit binds each extracted body's SHA-256, its exact citation,
length, official URL and displayed version bounds. All nine intervals cover
calendar year 2025. The release selector adds this scope to all twenty scopes
of the published context release, for 8,194 rows in 21 scopes.

The archive's displayed statutory validity is not an adjudication of
constitutional non-application, transition rules or every possible parentage
case. These remain separate encoding/review obligations. The tranche does
not assert that historical parentage source discovery is complete and does
not change a serving pointer or claim Kindergeld closure.
