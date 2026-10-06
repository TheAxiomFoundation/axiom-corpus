Add program bundles: `manifests/program-bundles/us-az-snap.yaml` lists the
documents of Arizona SNAP's two delivery tiers, each with the part of the
program it feeds and every exclusion's reason. Tier 1 (screener-level parity)
is the plan's documents and every PolicyEngine-US reference of one pinned
release (`scripts/export_policyengine_references.py`). Tier 2 (the full
document bundle) holds all of Tier 1, the federal law of the program section
by section from the SNAP needs-closure schema, Arizona's source manifests,
and the Arizona sources the corpus does not hold yet.
`scripts/build_program_bundle.py` builds it from one config file
(`us-az-snap.config.yaml`) that holds every choice as data.
