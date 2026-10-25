# 26 USC AMT and foreign-tax-credit sections

Release `us-2026-07-27-usc-amt-ftc-sections` adds exact normalized proof atoms
for 26 U.S.C. 27, 57–59, 901, 903, and 904. It also adds section 902 solely as
a repeal-status atom because operative section 904 continues to name it.

## Retained official source

The source is the immutable official OLRC Title 26 USLM release current through
Public Law 119-102, except 119-101, as of 2026-07-12:

- URL:
  `https://uscode.house.gov/download/releasepoints/us/pl/119/102not101/xml_usc26@119-102not101.zip`
- ZIP: 8,289,527 bytes; SHA-256
  `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0`
- Exact `usc26.xml` member: 55,856,053 bytes; SHA-256
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`

The retained XML is byte-equal to the ZIP member. It is not reserialized,
excerpted, line-ending-normalized, or hand-corrected. The normalized inventory
and provisions assign each target hierarchy its exact official House reader
URL:

| Section | Official reader URL | Rows |
|---|---|---:|
| 27 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section27&num=0&edition=prelim` | 1 |
| 57 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section57&num=0&edition=prelim` | 43 |
| 58 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section58&num=0&edition=prelim` | 17 |
| 59 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section59&num=0&edition=prelim` | 98 |
| 901 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section901&num=0&edition=prelim` | 131 |
| 902 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section902&num=0&edition=prelim` | 1 |
| 903 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section903&num=0&edition=prelim` | 1 |
| 904 | `https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title26-section904&num=0&edition=prelim` | 259 |

The shared title row brings the complete scope to 552/552 rows.

## Reproducible local generation

The retained source bytes, inventory, provisions, and coverage report are
reproduced by this literal command:

```bash
uv run --extra dev python scripts/repro/us_usc_amt_ftc_sections.py --base data/corpus
```

The script verifies both retained source hashes, the sole ZIP member, ZIP/XML
byte equality, exact per-section row counts, section-specific reader URLs, and
the repeal-only constraints on section 902. A second run into a fresh temporary
base was byte-compared against all five committed scoped artifacts.

## Section 902 boundary

The official section 902 element is marked `status="repealed"`, has a repeal
heading, and has no operative body or descendants. Operative section 904 text
still names section 902 at 904(d)(1), 904(d)(2)(E)(i)(II), and
904(d)(2)(F)(ii). The normalized section 902 row therefore retains only:

- `citation_path: us/statute/26/902`;
- the official repeal heading and source identity;
- `metadata.status: repealed`; and
- a blank body with no descendant rows.

It is not an operative 2026 credit rule and supplies no section 902 amount.

## Structural and citation-path findings

Every source-asserted target descendant survives in official document order.
None of these sections contains duplicate-numbered siblings, duplicate source
identifiers, skipped hierarchy levels, or mixed structural child ranks, so the
existing full-title collision regression is sufficient and no new traversal
fix is needed.

The new subsection paths deliberately move the unique-uppercase citation-path
ratchet from 6,327 to 6,710. The concurrent section 63/165 worker may need the
same `schema/citation-path.v1.json` census file; that shared-file conflict is
reported for integration rather than speculatively combining branch results.

No publication, R2 upload, Supabase load, release activation, push, GitHub
mutation, or RuleSpec repository change is part of this ingest. The local
environment has no ingest-signing key, so the main lane must apply the final
signature after the attested content commit is an ancestor.
