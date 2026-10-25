# Needs-driven closure check, 2026-09-11 corpus, ten board Year 1 programs

Question: does the corpus, as cut by `us-rulespec-2026-09-11-program-ingestion-union` plus the
2026-09-11 second-run scopes on disk, hold every source document family a complete encoding of each
program's rulebook needs, per jurisdiction? The bar is the law's own structure: every section of the
federal statute and implementing regulation, then each state's own rulebook (manual or regulation table
of contents, state plan, tables, transmittals). PolicyEngine is a cross-check column only, so the
`pe_modeled` field shows where the law has elements PolicyEngine does not model.

Each program has a `<program>-schema.yaml` (the elements and their carrying document families), a
`<program>-matrix.csv` with exactly one row per jurisdiction x element (status PRESENT with a cited
scope version and citation_path, or EXTRACTABLE, ABSENT, OUTREACH, REVIEW; federal elements are decided
once and marked INHERITED for states; N/A where the jurisdiction's law has no such rule), and a
`<program>.md` with method, roll-up, largest gap families and what closes them. Builders are checked
in so the check can be re-run. Percentages below are of state-level checked cells; every agent reports
a residual false-positive rate on PRESENT of roughly 10 to 20 percent, so the gap columns are floors.

| Program | Elements | Cells checked | Present | Extractable | Absent | Outreach | Review | Elements PE does not model |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| SNAP | 393 | 3443 | 77% | 6% | 6% | 2% | 9% | 286 |
| WIC | 110 | 1664 | 38% | 2% | 36% | 18% | 5% | 87 |
| Medicaid | 302 | 7385 | 50% | 29% | 6% | 5% | 10% | 261 |
| CHIP | 186 | 2733 | 50% | 35% | 0% | 6% | 9% | 170 |
| TANF | 181 | 1781 | 64% | 17% | 0% | 1% | 18% | 162 |
| CCDF | 99 | 1599 | 75% | 8% | 0% | 9% | 8% | 84 |
| SSI | 131 | 6812 | 48% | 50% | 1% | 0% | 1% | 97 |
| Liheap | 41 | 2132 | 33% | 59% | 2% | 0% | 5% | 37 |
| Medicare | 68 | 3536 | 37% | 60% | 0% | 1% | 2% | 38 |
| TAX | 206 | 1629 | 55% | 43% | 0% | 0% | 2% | 85 |
| **All ten** | 1717 | 32714 | 52% | 34% | 4% | 3% | 6% | 1307 |


## What closes the gaps, by leverage

1. **Federal statute and regulation layers never taken.** 42 U.S.C. for SNAP, WIC, TANF, SSI, LIHEAP
   and Medicare eligibility and premiums; 7 CFR 271, 272, 274, 276 to 285; 45 CFR 260 to 265 and 96
   subpart H; 42 CFR 406, 407, 408, 423 and 447 subpart A; 26 CFR part 1 and 31 IRC sections. Each
   missing federal section costs 51 cells. One eCFR and U.S. Code run.
2. **State plans filed with the federal agency.** CMS-posted Medicaid and CHIP state plans (about 3,700
   cells), FNS-posted SNAP E&T plans (50 states), TANF plans (49), WIC plans, CCDF Appendix 1 (51).
3. **Dollar figures in charts and attachments.** MSP income charts (36 states), LIHEAP benefit matrices
   (37), SSI supplement standards (10), FY2026 SNAP tables (15 to 25), TY2026 indexed tax amounts (30).
4. **Whole-chapter state statute and regulation for income tax.** 18 states hold only a handful of
   income-tax sections; no state income-tax regulation chapter is selected.
5. **Structural absences.** WIC: 20 states publish no manual, 10 gate it. Medicaid community
   engagement: absent in 48 states until the 2027 compliance date. Territories: most programs post nothing.
6. **Our own misses, fixable by selection or one extraction each.** Delaware TANF 3000-series never taken;
   HI, ME, MD, NC TANF rulebooks and TX, WY zero-liability tax scopes on disk but not selected; header-only
   stubs in DE, ME, KY, NH tax recovery rows; whole-chapter dumps used as section bodies in CT, OR, NC, NY, MI.

## Per-program indexes (appended by each agent)


One folder per pass over the board Year 1 programs: does the corpus hold every source-document
family a complete encoding of each program's rulebook needs, per jurisdiction (federal plus the
50 states and DC), and where it does not, is the gap extractable, absent, outreach, or review?

The bar is the law's own structure (statute, every CFR section, the state rulebook), not
PolicyEngine; PolicyEngine and rulespec-us are recorded per element as a cross-check that shows
where Axiom goes beyond them. Read-only with respect to `data/corpus`. Selected scopes are those in
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json`; the SNAP check also
treats the twelve `2026-09-11-<st>-snap-manual-supersede` scopes on disk as replacing their released
versions.

Files per program (`<program>` in lower case):

| File | Content |
| --- | --- |
| `<program>-schema.yaml` | the needs schema: every rule element a complete encoding must read, derived from the program's legal structure; `pe_modeled` and `rulespec_scoped` per element as a cross-check only |
| `<program>-matrix.csv` | one row per (jurisdiction, element): `jurisdiction, element, level, family, status, scope_version, citation_path, pe_modeled, evidence_note` |
| `<program>.md` | method, per-jurisdiction roll-up, top gaps by how many states share them, what would close each class, elements beyond PolicyEngine, schema uncertainty, timing and searches |

Status vocabulary (all programs): `PRESENT` (a specific provision body in a selected scope carries
the element; cited), `EXTRACTABLE` (the publisher lists the carrying family; not taken), `ABSENT`
(the publisher posts nothing carrying it; what was checked is in the note), `OUTREACH` (the queue row
records a publisher block), `REVIEW` (cannot tell from the evidence), `INHERITED` (federal-level
element decided once at the `us` row; the state row's note names the federal status).

## Index

| Program | Elements | Schema | Matrix | Report | Builder |
| --- | ---: | --- | --- | --- | --- |
| SNAP | 393 | [snap-schema.yaml](snap-schema.yaml) | [snap-matrix.csv](snap-matrix.csv) | [snap.md](snap.md) | `check_snap_wic.py` (schema + matrix + `summary.json` + `snap-hits.jsonl`), `write_snap_wic_reports.py` (report); `cfr_structure.py` holds the eCFR section lists for 7 CFR 246 and 271-285 |
| WIC | 114 | [wic-schema.yaml](wic-schema.yaml) | [wic-matrix.csv](wic-matrix.csv) | [wic.md](wic.md) | same builders (`wic-hits.jsonl`) |

Other programs' checks (Medicaid, CHIP, SSI, LIHEAP, Medicare, TANF, CCDF, tax) are run by their
own agents on sibling `analysis/needs-closure-*` branches; append their rows here when they land.



One folder per pass over the board Year 1 programs: does the corpus hold every source-document
family an end-to-end encoding of each program needs, per jurisdiction (federal plus the 50
states and DC), and where it does not, is the gap extractable, absent, outreach, or review?

Read-only with respect to `data/corpus`. Selected scopes are those in
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json` plus
`us/regulation/2026-09-11-title-42-part-436` (the federal CFR follow-on branch).

Files per program (`<program>` in lower case):

| File | Content |
| --- | --- |
| `<program>-schema.yaml` | the needs schema: every rule element a complete encoding must have, derived from the program's legal structure (statute, every CFR section, the state rulebook structure); PolicyEngine and rulespec-us recorded per element as a cross-check only |
| `<program>-matrix.csv` | one row per (jurisdiction, element): `jurisdiction, element, level, family, status, scope_version, citation_path, pe_modeled, evidence_note` |
| `<program>.md` | method, per-jurisdiction roll-up, top gaps by how many states share them, and what would close each class |
| `tools/` | the schema and matrix builders that produced the files (reproducible from `data/corpus` and the queues); `*_pass1.py` are the superseded 2026-09-11 builders kept for the audit trail, `search-universe.json` lists the scopes searched per state |

Status vocabulary (all programs): `PRESENT` (a specific provision in a selected scope carries the
element; cited), `EXTRACTABLE` (the publisher lists the carrying family; not taken),
`ABSENT` (the publisher posts nothing carrying it), `OUTREACH` (the queue row records a
publisher block), `REVIEW` (cannot tell), `INHERITED` (federal-only element counted once at the
`us` row), `NOT_APPLICABLE` (the element does not apply at that level, for example 42 CFR 436
for the 50 states, or a state-only element at the federal row).

## Index

| Program | Elements | Schema | Matrix | Report |
| --- | ---: | --- | --- | --- |
| Medicaid | 302 | [medicaid-schema.yaml](medicaid-schema.yaml) | [medicaid-matrix.csv](medicaid-matrix.csv) | [medicaid.md](medicaid.md) |
| CHIP | 186 | [chip-schema.yaml](chip-schema.yaml) | [chip-matrix.csv](chip-matrix.csv) | [chip.md](chip.md) |

Other programs' checks (SNAP, WIC, SSI, LIHEAP, Medicare, TANF, CCDF, tax) are run by
their own agents on sibling `analysis/needs-closure-*` branches; append their rows here when
they land.

The Medicaid and CHIP files are pass 2 (2026-09-12). Pass 1 (2026-09-11) was audited by
reading a random sample of its PRESENT cells and found too optimistic (hits in SNAP, TANF and
CalFresh scopes, table-of-contents lines, single-word patterns); `medicaid.md` and `chip.md`
record what changed and the residual false-positive rate estimated from the pass-2 sample.



One folder per program family. Each check asks: does the corpus hold every source
document family a complete encoding of the program's rulebook needs, per jurisdiction
(federal plus the 50 states and DC), and where it does not, is the gap EXTRACTABLE
(publisher lists the carrying document, not taken or not selected), ABSENT (publisher
posts nothing), OUTREACH (publisher blocks) or REVIEW (cannot tell from the evidence)?

The bar is the law's own structure (statute, CFR, state rulebook), not PolicyEngine;
PolicyEngine is a cross-check that shows where Axiom goes beyond it.

Files per program:

- `<program>-schema.yaml`: the needs schema (federal statute elements, every CFR
  section, state-level elements with the facts an encoder reads, PolicyEngine cross-check).
- `<program>-matrix.csv`: one row per jurisdiction x element with
  `jurisdiction, element, level, family, status, scope_version, citation_path, pe_modeled, evidence_note`.
  Federal-only elements have one row at `us` and are inherited by the 51 jurisdictions.
- `<program>.md`: method, per-jurisdiction roll-up, top gaps, what closes each class,
  elements beyond PolicyEngine, timing and searches.

## Index

| Program | Files | Builder |
| --- | --- | --- |
| TANF | `tanf-schema.yaml`, `tanf-matrix.csv`, `tanf.md` | `build_tanf_ccdf_matrix.py` (read-only over `data/corpus`; `summary.json` is its roll-up) |
| CCDF | `ccdf-schema.yaml`, `ccdf-matrix.csv`, `ccdf.md` | `build_tanf_ccdf_matrix.py` |

Other agents append their programs to this index.



Per program: `<program>-schema.yaml` (the law-derived needs schema), `<program>-matrix.csv` (one row per jurisdiction x element: jurisdiction, element, level, family, status, scope_version, citation_path, pe_modeled, evidence_note) and `<program>.md` (method, roll-ups, gaps, closers, elements beyond PolicyEngine).

## SSI, LIHEAP, Medicare (branch analysis/needs-closure-ssi-liheap-medicare)

| program | elements | cells | PRESENT | EXTRACTABLE | ABSENT | OUTREACH | REVIEW | PE does not model |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ssi | 131 | 6812 | 3291 | 3386 | 83 | 8 | 44 | 92 |
| liheap | 41 | 2132 | 712 | 1268 | 44 | 1 | 107 | 28 |
| medicare | 68 | 3536 | 1311 | 2132 | 7 | 18 | 68 | 38 |

Built by `build_ssi_liheap_medicare_matrices.py` (reads `data/corpus` read-only), checked by `verify_matrices.py`, reports by `write_reports.py`.



One folder per program family. Each check derives its needs schema from the law's own
structure (not from PolicyEngine), then asks, per jurisdiction and per element, whether a
provision body in a scope selected by
`docs/ingest-runs/2026-09-11-us-rulespec-program-ingestion-union.selector.json` carries the
fact, and if not whether the gap is EXTRACTABLE, ABSENT, OUTREACH or REVIEW (plus N/A where
the jurisdiction's law has no such rule). Every jurisdiction x element pair has exactly one
row in the program's matrix CSV. Corpus artifacts are read only.

| program | schema | matrix | report | generator |
|---|---|---|---|---|
| Income tax (federal + 50 states + DC, incl. EITC/CTC and state counterparts) | `tax-schema.yaml` | `tax-matrix.csv` | `tax.md` | `tax-check.py` (writes `tax-stats.json`) |

Other program families (SNAP/WIC, Medicaid/CHIP, TANF/CCDF, SSI/LIHEAP/Medicare) are checked
on sibling branches `analysis/needs-closure-*`; append their rows here when they land.

Matrix columns: `jurisdiction, element, level, family, status, scope_version, citation_path,
pe_modeled, evidence_note` plus `element_label` and `rulespec_encoded`.
