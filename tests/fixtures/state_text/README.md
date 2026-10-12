# Official statute text regression excerpts

These fixtures copy reduced operative-content excerpts from retained official
HTML snapshots in the `2026-07-13-recovery` scopes. All source sentences and
nested DOM structure within the chosen excerpts are retained. Page navigation,
footer content, section history, and unrelated subsections were omitted. HTML
serialization normalizes attribute quoting; the legal text is unchanged.

| Fixture | Official source | Retained content | Source snapshot SHA-256 |
| --- | --- | --- | --- |
| `maine-5111.html` | https://legislature.maine.gov/statutes/36/title36sec5111.html | Opening tax-imposition paragraph and subsection 1-F | `3a89c98ede970563865dec61bdf57e1f8239754134b098eba5e5ea0515eecf5c` |
| `maine-5124-C.html` | https://legislature.maine.gov/statutes/36/title36sec5124-C.html | Subsections 1-B and 2, all lettered paragraphs and nested amounts | `c3c2e1c66cd1ab062612c2ad6b93551586118f19ae909a17ba6959caf2e58886` |
| `maine-5126-A.html` | https://legislature.maine.gov/statutes/36/title36sec5126-A.html | Both operative subsections | `561487d22b2bd6082d76a650f76e04223015c4b988ab8ecd7e38f2a3ec179d0d` |
| `maine-5213-A.html` | https://legislature.maine.gov/statutes/36/title36sec5213-A.html | Opening applicability paragraph, 1(A), 1(A-1), 1(B)(1)-(2), 4, and 6 | `ff62b23f0198a8e956f9acc1e5f2d0b4fa5dd096e63cd9a9cd4f9b7b0c5fd10a` |
| `ohio-5747.02.html` | https://codes.ohio.gov/ohio-revised-code/section-5747.02 | Division (A)(3), both table schedules, and following 2026 rate | `960f9336ebcaf1ab4dbe7f75775224e52642d75f03d0f1afa7c134ff1d6c5c3a` |

Each excerpt contains source passages the previous extraction lost:

- Maine 5111: "A tax is imposed for each taxable year" before any subsection.
- Maine 5124-C: "The basic standard deduction is:", "$12,000", the head-of-household factor 1.5, the married-joint factor 2, "The additional standard deduction is the amount allowed under the Code, Section 63(c)(3).", and phaseout thresholds and denominators $80,000/$75,000, $120,000/$112,500, $160,000/$150,000.
- Maine 5126-A: the unlettered dependent definition referring to Code Section 152, the unlettered "applicable amount" introduction, and lettered thresholds $266,700, $293,350, $320,000, and half of the paragraph C amount.
- Maine 5213-A: opening applicability to tax years beginning on or after January 1, 2016; both base-credit definitions and their amounts; the nested income definition; phaseouts $10/$500, $15/$750, and $20/$1,000 with $20,000/$30,000/$40,000 thresholds; and all three subsection 6 exclusions.
- Ohio 5747.02: each schedule header and row, with the income-range cell followed by its tax cell. The 2024 rows contain $360.69 plus 2.75% and $2,394.32 plus 3.5%; the 2025 rows contain $342.00 plus 2.75% and $2,394.32 plus 3.125%.

Inline `.bhistory` spans remain in Maine excerpts to test the existing
history boundary: histories embedded in `.mrs-text` stay in the body for byte
compatibility; histories outside `.mrs-text` are metadata. Labels, inline links,
nested paragraph markers, and table headers remain in document order.

The three `legacy-*.html` fixtures are exact UTF-8 copies of the existing
small test-fixture constants, obtained with Python AST literal evaluation:
`SAMPLE_SECTION_HTML` and `SAMPLE_UNSUBDIVIDED_SECTION_HTML` from
`test_corpus_maine.py`, and `SAMPLE_OHIO_CHAPTER` from `test_corpus_states.py`.
Their golden assertions preserve existing extraction bytes without importing
the other test modules.

Generated fallback subsections with no `.mrs-text` also retain amendment
history embedded in their operative container, matching the legacy parser.
Amendment histories outside either a `.mrs-text` paragraph or such a fallback
subsection remain metadata excluded from the body.
