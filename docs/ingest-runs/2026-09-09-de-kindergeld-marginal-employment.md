# Kindergeld marginal-employment sources

The native GII adapter captures the complete MiLoG (32 rows) and MiLoV5 (4 rows), with zero missing or extra provisions. Official XML source snapshots, inventories and coverage are retained. Per-row body hashes and original XML hashes appear in the companion audit JSON.

SGB IV §8(1a), reached through EStG §32(4), defines the marginal-employment threshold using the statutory minimum wage. The preceding release retained MiLoV4 for2025 but lacked MiLoG and MiLoV5. MiLoV5 §1 expressly dates its13.90 EUR rate to1 January2026 and14.60 EUR rate to1 January2027; §2 supplies commencement. The capture does not substitute2026 rates for2025. Current MiLoG consolidation is not automatically the historical2025 version of every provision.

Reproduction: `PYTHONPATH=src python -m axiom_corpus.corpus.cli extract-de-gii --base data/corpus --version 2026-09-09-de-kindergeld-marginal-employment --manifest manifests/de-kindergeld-marginal-employment-gii.yaml --source-as-of 2026-09-09 --expression-date 2026-09-09`.

The additive release selector retains all37 preceding scopes and adds the statute and regulation scopes. No prior body, adapter code or serving activation is changed. These captures supply source evidence; they do not establish dependency closure or certification.
