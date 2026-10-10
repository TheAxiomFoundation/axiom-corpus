# Maryland Tax-General statute recovery repair

## Scope

- Jurisdiction: `us-md`
- Document class: `statute`
- Corpus version: `2026-07-13-recovery`
- Retrieval date: 2026-07-22
- Sections: Tax-General §§ 10-105 and 10-211

This run repairs the existing Maryland income-tax statute recovery in place.
Current release selectors already point to `2026-07-13-recovery`, so retaining
that version replaces the unusable artifacts without requiring unrelated
release-selector churn. The citation roots remain
`us-md/statute/gtg/10-105` and `us-md/statute/gtg/10-211`.

## Defect and repair

The prior recovery requested `article=ggt`. The Maryland General Assembly
served a `File Not Found` shell, and the recovered provisions contained only
account and site-navigation text even though coverage was marked complete.

The repaired manifest requests the official current codified pages with the
correct `article=gtg` parameter. Extraction is restricted to `#StatuteText`
and removes the Previous/Next button groups. Each section therefore produces
one body block containing the section text, plus its stable document root.
The obsolete extensionless shell captures and their hand-written provenance
records are removed; the normal official-document pipeline records the fetched
HTML, URL, timestamp, content type, hash, and source metadata directly in the
inventory and provisions.

## Authority and limitations

The Maryland General Assembly is the primary official source for the codified
statute text. `source_as_of` and `expression_date` record the 2026-07-22 current
codified-text retrieval, not a claim that the MGA page supplies a complete
historical effective-date chain.

This repair does not certify RuleSpec semantics, PolicyEngine parity, a final
2026 resident return, or comprehensive Maryland income-tax coverage. The 2025
resident Form 502 booklet and Technical Bulletin 58 are useful supplemental
authorities, but they belong in separately signed `form` and `guidance` scopes.
They are intentionally deferred so they cannot be mistaken for the controlling
statutory scope or for 2026 final-return instructions.
