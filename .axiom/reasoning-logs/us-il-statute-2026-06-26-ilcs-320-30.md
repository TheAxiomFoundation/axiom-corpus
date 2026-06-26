# Illinois Senior Citizens Real Estate Tax Deferral Act ingest

## Scope

- Jurisdiction: `us-il`
- Document class: `statute`
- Scope: `320 ILCS 30`
- Source as of: `2026-06-26`
- Expression date: `2026-06-26`

## Command

```bash
env -u UV_FROZEN uv run --extra dev axiom-corpus extract-illinois-ilcs --base data/corpus --version 2026-06-26-ilcs-320-30 --only-chapter 320 --only-act 30 --source-as-of 2026-06-26 --expression-date 2026-06-26 --workers 4
```

## Source decision

The Illinois ILCS adapter uses the official ILGA FTP directory to discover and order ILCS document names. During this run, the FTP section HTML for `320 ILCS 30/2` and `320 ILCS 30/3` was stale relative to the current official ILGA `fulltext.asp?DocName=...` pages.

The adapter was therefore repaired to keep FTP discovery/order, but fetch section bytes from the official current `https://www.ilga.gov/legislation/ilcs/fulltext.asp?DocName=<stem>` endpoint. Container documents continue to use FTP because the fulltext endpoint only serves section documents.

The resulting provision text includes P.A. 104-452, effective 2025-12-12, including:

- Maximum household income of $77,000 for tax year 2026 and $79,000 for tax years 2027 and thereafter.
- Annual deferral cap of $7,500 for tax year 2022 and every tax year after.

## Validation

- Extracted 10 provisions: one chapter container, one act container, and eight sections.
- Coverage comparison is complete: 10 source inventory rows matched 10 provision rows, with no missing or extra provisions.
- Focused Illinois adapter tests passed after the source URL repair.
