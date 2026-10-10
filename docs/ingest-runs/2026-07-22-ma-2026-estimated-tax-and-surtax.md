# Massachusetts 2026 estimated tax and surtax guidance

This intake retains two separate official Massachusetts Department of Revenue
sources. The first is the tax-year-2026 Form 1-ES estimated-tax booklet. The
second is the current DOR surtax-calculation guidance, retained separately
because it materially clarifies how negative Part A, Part B, and Part C
amounts affect the surtax base.

## Form 1-ES estimated-tax scope

Official source:
<https://www.mass.gov/doc/2026-form-1-es-estimated-tax-payment-vouchers-instructions-and-worksheets/download>

The retained seven-page PDF has SHA-256
`d5bdb884a9b70a2b5c04356e58a7edcdccd59ce6841bf1550409b6d9c99f0d19`.
Its metadata identifies the Massachusetts Department of Revenue as author,
records a January 14, 2026 creation date, and records a February 5, 2026
modification date.

The generic official-document adapter snapshots the complete PDF and produces
one document container plus one body-bearing provision at
`us-ma/form/individual-income-tax/2026/1-es/document-1`. Page 3 assigns a 5%
rate to the listed ordinary-income categories. It also instructs filers to add
column A of lines 1 through 2c, subtract the tax-year-2026 $1,107,750 surtax
threshold, and multiply the result by 4%. Coverage is complete at two
inventory citations and two normalized provisions.

This is an estimated-tax source. The intake does not claim that Form 1-ES is a
final tax-year-2026 Form 1 or Form 1-NR/PY liability schedule, and it does not
assert RuleSpec semantics or PolicyEngine parity.

## Surtax-guidance scope

Official source:
<https://www.mass.gov/info-details/massachusetts-4-surtax-on-taxable-income>

The retained HTML has SHA-256
`20332177fd5030dfdfbe1f74543a7a65d1aa8e9daf61a267c34c509418d4c081`.
Two consecutive source fetches produced identical bytes. The page states that
it was updated June 1, 2026. Direct browser impersonation is required to pass
the site's access layer; the manifest records that request configuration so
the fetch remains reproducible.

An anchored extraction begins at `calculating-income-subject-to-the-4-surtax`
and stops before `forms--electronic-filing-requirements`. It produces one
document container plus one body-bearing provision at
`us-ma/guidance/department-of-revenue/4-percent-surtax/2026/taxable-income-calculation`.
The retained section publishes the $1,107,750 threshold and 4% formula. It also
states that the surtax base sums Part A, Part B, and Part C taxable income,
treats a negative amount in any Part as zero, and does not permit a negative
Part to reduce another Part after any cross-Part deductions otherwise allowed
by statute. Coverage is complete at two inventory citations and two normalized
provisions.

The guidance is kept separate from Form 1-ES because it clarifies the
positive-Parts boundary. It does not certify all inputs, deductions, credits,
or other rules needed for a complete final-return calculation.

## Statutory authority and generation

The existing body-bearing provision `us-ma/statute/62/4/block-2` in corpus
version `2026-07-13-recovery` supplies the statutory rate and positive-Parts
structure. The official Form 1-ES and guidance snapshots supply DOR's
tax-year-2026 indexed threshold and administrative presentation of the
calculation.

The scopes are generated without publication or database loading:

```bash
uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-22-ma-2026-form-1-es \
  --manifest manifests/us-ma-2026-form-1-es.yaml

uv run --extra dev axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-07-22-ma-2026-surtax-guidance \
  --manifest manifests/us-ma-2026-surtax-guidance.yaml
```

Repeating both extractions produced identical source, inventory, provision,
and coverage hashes. The protected signing wrapper creates a distinct signed
ingest manifest for each scope; no private signing material is read, printed,
or written by the ingestion session.
