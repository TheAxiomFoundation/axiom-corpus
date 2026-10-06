Add program bundles: `manifests/program-bundles/us-az-snap.yaml` lists the
documents of Arizona SNAP's two delivery tiers (screener-level parity and the
full document bundle), each with the part of the program it feeds and every
exclusion's reason. `scripts/build_program_bundle.py` builds it from one
config file (`us-az-snap.config.yaml`) that holds every choice as data, and
from committed inputs: the plan's document list and the PolicyEngine-US
references.
