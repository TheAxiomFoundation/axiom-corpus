# Indiana SSP SAPN source ingest

This run supports the PolicyEngine-parity surface for Indiana State
Supplementary Payments (`in_ssp`) by adding the current official FSSA source for
Supplemental Assistance for Personal Needs.

## Source selection

- Indiana Code is already tracked as a published source-first state-statute
  release (`us-in-code`, version `2026-05-05`) from the official Indiana
  General Assembly HTML release. The SAPN chapter cites IC 12-15-32-6.5 and
  405 IAC 7-1-1 for the statutory/regulatory benefit calculation authority.
- Indiana FSSA OMPP publishes Medicaid Policy Manual Chapter 5000 as a direct
  official PDF. Chapter 5000 states the SAPN eligibility and benefit calculation
  rules needed before RuleSpec encoding.
- The current IGA/IAR public web apps serve JavaScript shells to unattended
  HTTP clients, and the public API requires an API key. This ingest therefore
  does not duplicate Indiana Code or IAC artifacts from secondary mirrors.

## Command

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-04-in-ssp-sapn \
  --manifest manifests/us-in-ssp-sapn-official-documents.yaml
```

## Result

- Jurisdiction: `us-in`
- Document class: `manual`
- Version: `2026-07-04-in-ssp-sapn`
- Source files: 1
- Provisions written: 8
- Coverage: complete

The signed ingest manifest covers the source snapshot, inventory, provision
JSONL, and coverage report.
