# Unemployment insurance benefits, wave 4: five states with no statute adapter

Date: 2026-11-24 (America/New_York). Branch `ingest/ui-benefits-tier1-wave4`, stacked on
`ingest/ui-benefits-tier1-wave3`. Earlier notes: `2026-11-24-ui-benefits-wave1.md`, `2026-11-24-ui-benefits-wave1b.md`,
`2026-11-24-ui-benefits-wave3.md`.

Input: the roadmap's UI scope audit (`axiom-roadmap-dashboard` a9a977bc; no person reviewed it). Each citation was
checked against the fetched official text. Nothing was signed, locked, loaded, pushed to R2 or published. No adapter
was changed. No CAPTCHA or challenge page was worked around.

States: Arkansas, Mississippi, North Carolina, Virginia, Wyoming. None has a statute adapter that reads its
unemployment law, so the statutes are taken with `extract-official-documents`, as earlier runs took the North Carolina,
Virginia and Wyoming tax and welfare statutes.

## Scopes

12 scopes, 335 rows, 301 with text. Every scope reports coverage `complete: true`.
`scripts/validate_citation_paths.py` over the new files: `RESULT: OK`. No path of these scopes is in a scope of the
pin-line selector. All are ready to sign.

| jurisdiction | class | version | rows | rows with text | characters |
| --- | --- | --- | ---: | ---: | ---: |
| us-ar | guidance | `2026-11-24-ui-benefits-guidance-ar` | 18 | 17 | 27,330 |
| us-ar | statute | `2026-11-24-ui-benefits-statute-ar` | 2 | 1 | 27,828 |
| us-ms | guidance | `2026-11-24-ui-benefits-guidance-ms` | 20 | 17 | 22,738 |
| us-ms | regulation | `2026-11-24-ui-benefits-regulation-ms` | 66 | 65 | 159,214 |
| us-ms | statute | `2026-11-24-ui-benefits-statute-ms` | 6 | 4 | 532,295 |
| us-nc | guidance | `2026-11-24-ui-benefits-guidance-nc` | 25 | 22 | 34,842 |
| us-nc | regulation | `2026-11-24-ui-benefits-regulation-nc` | 43 | 42 | 50,655 |
| us-nc | statute | `2026-11-24-ui-benefits-statute-nc` | 14 | 7 | 28,650 |
| us-va | guidance | `2026-11-24-ui-benefits-guidance-va` | 24 | 22 | 37,341 |
| us-va | regulation | `2026-11-24-ui-benefits-regulation-va-title-16-agency-5-chapter-60` | 9 | 5 | 14,716 |
| us-va | statute | `2026-11-24-ui-benefits-statute-va` | 12 | 6 | 15,006 |
| us-wy | statute | `2026-11-24-ui-benefits-statute-wy` | 96 | 93 | 186,443 |

How each layer is read:

- **North Carolina**: seven G.S. chapter 96 section pages of ncleg.gov (`us-nc/statute/96/<section>`); 04 NCAC 24B
  from the Office of Administrative Hearings PDF, one row for each of its 42 rules; three DES documents. The DES pages
  leave a `<header>` element open, so the manifest keeps `header` out of the default drops and selects `article`.
- **Virginia**: six Code of Virginia title 60.2 section pages (`us-va/statute/60.2/<section>`); 16VAC5-60 complete
  (sections 10 to 40) from the existing `extract-virginia-vac` adapter; the VEC claimant handbook and the news release
  of 2026-06-25.
- **Wyoming**: chapter 3 of the Legislature's Title 27 PDF (file dated 2026-05-08), pages 13 to 107, one row for each
  of its 95 sections (`us-wy/statute/title-27/chapter-3/<section>`).
- **Mississippi**: two acts as approved (2013 House Bill 932, approved 2013-03-06; 2023 Senate Bill 2810, approved
  2023-04-17), the MDES regulations PDF, two MDES pages and form UI-505.A. Each act is one block of text: it holds
  many sections other than the cited ones, which is why the statute scope has 532,295 characters.
- **Arkansas**: Act 196 of 2023 and the 2026 claimant handbook.

## The audit against the official text

Confirmed in the extracted text under the cited number: G.S. 96-1, 96-14.1, 96-14.2, 96-14.3, 96-14.9, 96-14.13,
96-15.01; Va. Code 60.2-204, 60.2-602, 60.2-603, 60.2-604, 60.2-607, 60.2-612; 16VAC5-60-10 and -20; W.S. 27-3-102,
27-3-303, 27-3-304, 27-3-306, 27-3-313; the current amounts on the agency documents of all five states.

Differences and limits:

- **Virginia 60.2-602**: the Code page prints "SEE PRINTED BILL FOR TABLES" in place of the benefit table and the
  duration table, as the audit said. The tables are not in the corpus. The 2026 act that raised the amounts was not
  taken (the audit found its page needs scripts).
- **Wyoming 27-3-306**: the catchline names a waiting period, but the current text has none (paragraph (a)(iv) and
  subsection (c) are repealed, Laws 2005, ch. 186).
- **Mississippi 71-5-503 and 71-5-507** (weekly benefit amount and duration): the audit read them in 2025 House Bill
  1577 as introduced, which is not law. Neither act taken here sets them out; 2013 House Bill 932 only refers to them.
  They are not in the corpus. The official code is on a LexisNexis portal, which this run did not try.
- **Mississippi 71-5-505**: set out in the 2013 act only (earnings over $40 are deducted; one waiting week). The 2023
  act does not set it out, so a later amendment is possible.
- **Mississippi 71-5-11, 71-5-511, 71-5-513**: set out in the 2023 act (reenacted).
- **Arkansas 11-10-504**: Act 196 of 2023 sets out subsection (a) as amended (twelve times the weekly benefit amount
  or one-third of base period wages), in bill form with struck and underlined text.

## Not taken

| item | reason |
| --- | --- |
| Arkansas Code 11-10-201, -502, -503, -507, -517, -522 | the official code is on a LexisNexis site that the audit found puts each section behind a CAPTCHA; not tried |
| Arkansas 11 CAR part 1 | the Code of Arkansas Rules page has no rule text without scripts |
| Mississippi 2025 House Bill 1577 (71-5-503, 71-5-507) | an introduced bill, not law |
| Wyoming DWS page "What is Unemployment Insurance?" | dws.wyo.gov answered HTTP 504 on each attempt (2026-11-24); the audit met the same |
| Wyoming DWS unemployment rules | rules.wyo.gov needs an interactive search; the audit confirmed no address; not tried |

Each held document is in the generator's `HELD` list with its reason.

## Human steps

1. Sign and lock, after the scopes of waves 1, 1b and 3, with `AXIOM_CORPUS_INGEST_PRIVATE_KEY` and R2 write access:

   ```bash
   tail -n +2 docs/ingest-runs/2026-11-24-ui-benefits-wave4-unsigned-scopes.tsv |
   while IFS=$'\t' read -r j c v note; do
     uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction "$j" --document-class "$c" --version "$v" \
       --command "rebuild: see $note" --lock --push < /dev/null || break
   done
   git add .axiom/ingest-manifests .axiom/corpus-locks
   ```

2. Run `content-check` on the locked scopes.
3. Add the scopes to the draft successor selector before it is cut. Publish only; do not activate.

The artifacts are in the worktree's `data/corpus` and in a copy under `~/.axiom/workspace/ui-benefits-2026-11-24`.

## Rebuild

```bash
B=data/corpus
uv run python scripts/build_ui_benefits_document_manifests.py
for m in manifests/us-{ar,ms,nc,va,wy}-ui-benefits-*.yaml; do
  uv run axiom-corpus-ingest extract-official-documents --base $B --manifest $m \
    --version "$(grep -m1 '^version:' $m | awk '{print $2}')"
done
uv run axiom-corpus-ingest extract-virginia-vac --base $B --version 2026-11-24-ui-benefits-regulation-va \
  --only-title 16 --only-agency 5 --only-chapter 60 --source-as-of 2026-11-24 --expression-date 2026-11-24
```

Impact analysis: the GitNexus tools were not available in this session; no library code changed in this run.
