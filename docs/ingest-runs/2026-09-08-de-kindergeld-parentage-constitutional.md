# Constitutional applicability of the archived parentage rules

This scope retains the full German decision content from the official
Bundesverfassungsgericht publications for case 1 BvR 2017/21: the judgment
of 9 April 2024 and the order of 3 June 2025. They declare incompatibility
of BGB §1600(2) and (3) sentence 1 and govern continued application and
requested suspension of challenge proceedings. The 2025 order extends the
outer deadline to 31 March 2026, subject to earlier replacement legislation.
The precise conditions must be encoded from these texts; an archive's
statutory validity dates alone cannot replace them.

```sh
PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-official-documents --base data/corpus --version 2026-09-08-de-kindergeld-parentage-constitutional --manifest manifests/de-kindergeld-parentage-constitutional.yaml
```

The existing anchor-range extraction retains the complete `.c-decision`
container, including headnotes, operative orders and reasons. Publisher links
inside the container remain intact. Two HTML snapshots produce two root rows
and two content rows. The audit binds body SHA-256, length and verified
operative spans. The 2024 full judgment is long and may require separately
receipted bounded context for an encoder prompt; it is not truncated here.

This adds one guidance scope to the historical-parentage release selector:
8,198 rows in 22 scopes, retaining all twenty prior context-release scopes.
The supported guidance namespace records court identity and decision type
in metadata. No claim of BStBl II publication, full precedent enumeration,
encoded applicability or certification is made. No serving pointer changes.
