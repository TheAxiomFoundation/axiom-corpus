# Florida individual income-tax zero-liability authority (2026-07-24)

This scope preserves four official primary authorities that establish the
complete annual resident individual income-tax result for a natural person in
Florida.

Article VII, section 5(a) of the current Florida Constitution constrains taxes
on the income of natural persons who are residents or citizens of Florida.
Section 220.02(1), Florida Statutes, supplies the operative statutory
construction: chapter 220 is not intended to tax and may not be construed to
tax a natural person operating individually, as a proprietor or partner, or as
a member or manager of a limited liability company classified as a partnership
for federal income-tax purposes. It directs that this construction receive
preeminent consideration to avoid conflict with article VII, section 5.
Section 220.03(1)(z) independently limits the chapter 220 definition of
`taxpayer` to a corporation subject to the tax imposed by that code.
Chapter 2026-137, Laws of Florida, provides the enacted tax-year-2026
freshness check: section 1 amends only section 220.03(1)(n) and (2)(c), not
the paragraph (1)(z) taxpayer definition.

Together these authorities support an input-independent zero annual resident
individual income-tax liability for a natural person for tax year 2026. The
scope does not cover corporate or other artificial-entity income tax, tax at
the entity level on a corporation that is a partner, payments, filing
administration, local taxes, or nonresident allocation.

Artifacts are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-24-fl-individual-income-tax-zero-liability \
  --manifest manifests/us-fl-individual-income-tax-zero-liability.yaml
```

The three HTML selectors preserve only article VII, section 5 and sections
220.02 and 220.03 rather than navigation or unrelated constitutional and
statutory provisions. The four-page session law is preserved as one block so
that its amendment scope and enactment provisions remain together.
