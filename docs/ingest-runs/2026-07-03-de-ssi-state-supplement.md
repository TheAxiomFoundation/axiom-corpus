# Delaware SSI state supplement corpus ingest

This run supports the PolicyEngine-parity surface for Delaware State
Supplementary Payments (`de_ssp`) using primary/upstream official sources.

## Source selection

- Delaware Administrative Code Title 16 DSSM 13000 is the state regulation
  source for Delaware Medicaid categories. It identifies Delaware as a 1634
  state and states that SSA determines State Supplementary Payment eligibility
  for individuals residing in adult residential care arrangements.
- SSA POMS SI 01415.058 is the current SSA source for federally administered
  optional supplementary payments. The Delaware subsection provides the 2026
  living-arrangement OS codes and payment levels used by SSA.

The older SSA Philadelphia POMS page and SSA state-assistance summary were
reviewed as supporting discovery material, but this ingest keeps the active
RuleSpec grounding on current SSA POMS plus Delaware AdminCode.

## Commands

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-de-ssi-state-supplement-poms \
  --manifest manifests/us-de-ssi-state-supplement-poms.yaml
```

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-03-de-dssm-13000 \
  --manifest manifests/us-de-dssm-13000.yaml
```

## Results

- `us-de/guidance/2026-07-03-de-ssi-state-supplement-poms`: 1 official SSA
  POMS HTML source, 5 provision rows, complete coverage.
- `us-de/regulation/2026-07-03-de-dssm-13000`: 1 official Delaware AdminCode
  PDF source, 25 provision rows, complete coverage.

The POMS extraction selects only the Delaware subsection from the multi-state
POMS page. The generated rows include the certified adult residential care
living arrangement definition and the January 1, 2026 supplement levels:
$140 for an individual and $448 for a couple.
