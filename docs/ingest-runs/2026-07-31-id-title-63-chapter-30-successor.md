# Idaho Title 63 Chapter 30 retained-source successor

The released `us-id/statute/2026-07-13-recovery` scope retained five complete
official Idaho Legislature HTML pages but normalized them through the generic
document recovery path. That path emitted navigation-only child blocks and a
bodyless document container for each statute.

This repair leaves that historical scope unchanged. It copies the exact retained
official bytes into the immutable successor
`2026-07-31-id-title-63-chapter-30-successor` and routes them through the existing
Idaho section parser. The new scope contains the Title 63 and Chapter 30
containers plus native section records for 63-3022D, 63-3022E, 63-3024,
63-3024A, and 63-3025D. It contains no generic navigation blocks.

The named release `us-rulespec-2026-07-31-idaho-statutes-current` succeeds
`us-rulespec-2026-07-24-snap-cms-pit-union` and replaces only the Idaho statute
selector.

## Reproduction

```bash
uv run --extra dev python \
  scripts/repro/idaho_title_63_chapter_30_successor.py \
  --base data/corpus
```

The protected corpus wrapper signs the generated scope without exposing private
key material. Publication, database loading, release activation, RuleSpec
changes, and merge are separate reviewed steps.
