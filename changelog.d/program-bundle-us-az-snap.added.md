Add program bundles for the 13 core programs (SNAP, Medicaid, CHIP, TANF,
SSI, CCDF, LIHEAP, WIC, UI, Medicare, EITC, CTC and individual income tax):
`manifests/program-bundles/<program>.yaml` lists each program's documents
per delivery tier, for the federal layer once and for each state and DC.
Tier 1 (screener-level parity) is every PolicyEngine-US reference of the
newest release (`scripts/export_policyengine_references.py`), in the layer of
the law it names, and the plan's documents. Tier 2 (the full document bundle)
holds Tier 1, the federal law of the program from its needs-closure schema,
the federal guidance manifests, each state's manifests for the program, and
known sources the corpus does not hold yet. `scripts/build_program_bundle.py`
builds them from one config (`programs.config.yaml`) that holds every choice
as data.
