# 2026-07-03 New Jersey WFNJ Rules Ingest

## Scope

This run adds a source-first manifest for the current compiled New Jersey
Administrative Code chapter governing Work First New Jersey:

- Jurisdiction: `us-nj`
- Document class: `regulation`
- Version: `2026-07-03`
- Root citation path: `us-nj/regulation/njac-10-90`
- PE parity surface: `nj_wfnj`

## Source Hierarchy

The existing New Jersey statute adapter already ingests the official New
Jersey Legislature `STATUTES-TEXT.zip` source for `us-nj/statute/*`. The WFNJ
regulation chapter cites chapter authority at `N.J.S.A. 30:1-12` and is
downstream of the Work First New Jersey Acts in Title 44, including
`N.J.S.A. 44:10-44` and `N.J.S.A. 44:10-55`.

PolicyEngine's offline New Jersey WFNJ references pointed to Lexis Advance
copies of `N.J.A.C. 10:90-3.3` and `10:90-3.9`. I did not use Lexis as the
corpus source. The public official source used here is the New Jersey
Department of Human Services rules-and-regulations PDF for the compiled
`N.J.A.C. 10:90` chapter.

## Source

- URL: `https://www.nj.gov/humanservices/notices/documents/rules-and-regulations/WFNJ_Manual_12.17.24.pdf`
- Source authority: New Jersey Department of Human Services, Division of Family Development
- Official publisher named in the PDF: New Jersey Office of Administrative Law
- Expression date: `2024-12-16`
- Source-as-of: `2026-07-03`

The PDF states that it includes regulations adopted and published through the
New Jersey Register, Vol. 56 No. 24, December 16, 2024.

I also checked the 2024 adoption PDF
`R.2024 d.120 (56 N.J.R. 2335(b))`, which updates `N.J.A.C. 10:90-3.9` and
`10:90-3.18`; the compiled chapter PDF already contains that adopted language.

## Extraction

Command:

```bash
uv run --project /Users/maxghenis/TheAxiomFoundation/_worktrees/axiom-corpus-nj-wfnj-20260703 \
  axiom-corpus extract-official-documents \
  --base /Users/maxghenis/TheAxiomFoundation/_worktrees/axiom-corpus-nj-wfnj-20260703/data/corpus \
  --version 2026-07-03 \
  --manifest /Users/maxghenis/TheAxiomFoundation/_worktrees/axiom-corpus-nj-wfnj-20260703/manifests/us-nj-wfnj-rules.yaml
```

Result:

- Source files: 1
- Source records: 245
- Provision records: 245
- Coverage: complete
- Key generated paths:
  - `us-nj/regulation/njac-10-90/10-90-3.3`
  - `us-nj/regulation/njac-10-90/10-90-3.8`
  - `us-nj/regulation/njac-10-90/10-90-3.9`

The labeled-section extractor drops repeated section headings from page
continuations and normalizes the `N.J.A.C. 10:90` sections into stable
section-level provision paths.
