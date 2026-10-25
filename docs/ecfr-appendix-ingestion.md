# Opt-in eCFR appendix ingestion

The eCFR inventory and extraction commands include parts, subparts, and sections
by default. Add `--include-appendices` to both commands when a new ingestion run
should also contain supported part appendices:

```bash
axiom-corpus-ingest inventory-ecfr --base /tmp/ecfr-604 \
  --version 2026-08-30 --as-of 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices
axiom-corpus-ingest extract-ecfr --base /tmp/ecfr-604 \
  --version 2026-08-30 --as-of 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices
```

Use a separate run/version when changing the intended scope of an existing
artifact. These commands write local artifacts; publication is a separate step.
The Python functions `build_ecfr_inventory`,
`build_ecfr_inventory_from_structures`, `iter_ecfr_title_provisions`, and
`extract_ecfr` expose the same keyword, `include_appendices=False` by default.

Supported identifiers are `Appendix A to Part 604` and equivalent single-letter
or numeric appendix identifiers. Their citation paths are
`us/regulation/45/604/appendix-a`; the parent remains the enclosing part, including
when a source subject group or subpart contains the appendix. Traversal preserves
source order without converting a provision twice.

Opted-in inventory construction rejects unsupported nonreserved identifiers,
including `Appendix to Subpart K of Part 416` and multi-letter identifiers such
as `Appendix II to Part 604`. A parsed part that contradicts the enclosing part
also fails validation. These errors do not imply full appendix coverage.
Exact `--section` selectors exclude appendices before validation. The lower-level
iterator likewise applies an explicit citation allowlist before converting an
appendix; selected unsupported identifiers still fail closed.
Appendix inventory/selection validation errors from either CLI command print a
diagnostic to stderr and exit with status 2 before writing run artifacts; an
existing run is preserved. Later parsing or I/O failures can occur after source capture.

For included appendices, extraction archives official PNG bytes for source
images, retains image references in the body, and keeps HD1–HD3 heading text.
Image-only forms therefore retain a nonempty body pointing to the captured
source. Existing SHA-256-bound formula transcription checks still apply. Image
references are source evidence, not OCR text or an executable formula.

When an inventory lists a supported appendix absent from the retained XML,
the existing structure-only fallback preserves its source identity with
`body=None`, `structure_only=True`, and `body_status=not_in_ecfr_full_xml`.
Inventory coverage alone does not imply that every provision has extracted text.

The offline recovery scripts `scripts/recover_ingest.py` and
`scripts/recover_ingest_batch.py` support section-only eCFR recovery. They cannot
replay an appendix-enabled run's inventory scope and archived graphics. Both
refuse `include_appendices: true`, appendix citations (including descendants) in
`covers_citation_paths`, or replacement of a destination inventory containing
appendices. This preflight runs before artifact writes, including in dry runs;
the batch also checks before reusing a previous success report and aborts without
rewriting that report. XML containing excluded appendices remains valid for
ordinary section-only recovery. Preserve appendix artifacts and use an
appendix-aware inventory/extraction workflow for a separate run instead; these
recovery scripts do not certify an appendix replay as complete.

Ordinary section rendering and formula-only image capture retain their prior
behavior, even in an appendix-enabled run. This change does not add HD1–HD3 text
or non-math image capture to sections. It also does not repair the inherited
loss of a nested `MATH` marker inside a consumed paragraph, table, or heading;
standalone `MATH` transcription and markers remain supported.

The retained 20 CFR 416 source remains a 622-entry inventory by default, and its
approved 14-record deeming slice reproduces the prior producer's bytes. The
[baseline manifest and replay instructions](validation/us-cfr-416-deeming-baseline.md)
distinguish that replay from the older published July provisions file.
