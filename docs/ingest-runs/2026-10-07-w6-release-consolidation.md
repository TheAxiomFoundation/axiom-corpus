# Wave-6 release consolidation: draft selector us-rulespec-2026-10-07-w6-bundle-gaps-union

Date: 2026-10-07
Controller pass that turns the nine wave-6 program-bundle-gap runs of 2026-10-06 (draft PRs #786-#794, branches
`discovery/ingest-w6-{federal,tax-al-hi,tax-ia-mi,tax-mn-oh,tax-ok-wv,tanf-ccdf-ak-ne,tanf-ccdf-nh-wy,health,benefits}`)
into the seventh selector of the union lineage. Branch `release/2026-10-07-w6-bundle-gaps`, cut from `main` (e16ccb799)
in the sparse worktree `~/axiom-corpus-worktrees/w6-release` (`data/corpus/` excluded); the nine branches are merged into
it. Everything here is local and unsigned: the artifacts live under `/Users/pavelmakarchuk/axiom-corpus/data/corpus` on
the controller's machine only. Nothing was signed or locked, nothing was written to R2 or Supabase, no PR was merged.

Draft selector: `docs/ingest-runs/2026-10-07-us-rulespec-w6-bundle-gaps-union.selector.json`
(`us-rulespec-2026-10-07-w6-bundle-gaps-union`, quality profile `complete-expression-dates-v1`, **1,445 scopes**). It
stays outside `manifests/releases/` for the reason the 2026-09-11, 2026-09-13 and 2026-09-14 drafts did: CI
deep-validates every tracked selector against committed (now: locked) artifacts, so it can be tracked only after the
signing commit. No open PR and no file on `main` uses the name.

## Base: the current release truth

- Serving: on 2026-10-07 every one of the 287 US `(jurisdiction, document_class)` pairs in `corpus.active_scope_pointer`
  (one read-only REST read) points at `us-rulespec-2026-09-14-wave4-union` (activated 2026-09-14T21:46Z). Nothing later
  is active.
- Union lineage on `main`: `us-rulespec-2026-09-14-wave4-r2-union` (1,042 scopes) is the newest selector that extends
  the activated one; it differs from it only by the five r2 scopes (NE, DE, AL statute; CT, CO regulation).
- Two later released selectors on `main` belong to the small RuleSpec-pin lineage (270-273 scopes, successors of
  `us-rulespec-2026-08-23-canada-338-suspension-union` and `us-rulespec-2026-08-08-obbb-alien-snap`). Their new scopes
  are carried here, so this cut supersedes them for the pairs they touch: `us/guidance/2026-09-24-snap-fy2027-cola`,
  `us/form/2026-09-24-irs-optional-sales-tax-tables-ty2021`, `us/form/2026-09-24-irs-optional-sales-tax-tables-ty2022-2025`,
  and the two table-preserving swaps of `us-rulespec-2026-09-24-irs-sales-tax-tables-union`
  (`...ca-wic-calworks-...-r2026-09-24-preserve-tables`, `...income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7-r2026-09-24-preserve-tables`
  in place of their originals). This also subsumes the two draft selectors on `main`,
  `2026-09-24-ca-leginfo-preserve-tables.selector.json` and `2026-09-23-tax-statute-policybench.selector.json` (its one
  scope is re-selected below).
- Pair check (script): every scope that `wave4-union` serves is in this selection except 19, each accounted for: the
  three r2 drops, the two CA preserve-table swaps, and the 14 released scopes replaced below. The selection carries
  317 pairs, 30 of them new.

## Arithmetic

1,042 (wave4-r2) + 3 (2026-09-24 additions; the two CA swaps are net 0) = 1,045
− 14 released scopes replaced (12 by consolidated successors, 2 by swaps)
+ 366 wave-6 scopes as extracted
+ 18 wave-5 scopes (2026-09-15) cited ALREADY-HELD
+ 16 signed scopes on `main` in no union selector, cited ALREADY-HELD
+ 14 consolidated successors
= **1,445**.

| Run (PR) | On disk | Selected as extracted | Into a successor | Not selected |
| --- | ---: | ---: | ---: | --- |
| federal (#786) | 18 | 16 | 1 (26 CFR part 1) | 1 held out (42 U.S.C. 1396a/b/d/p, decision) |
| tax-al-hi (#790) | 27 | 27 | 0 | |
| tax-ia-mi (#788) | 31 | 31 | 0 | |
| tax-mn-oh (#792) | 38 | 32 | 0 | 6 superseded first-run scopes (the `-r2` versions are selected) |
| tax-ok-wv (#787) | 37 | 36 | 1 (ORS 315) | |
| tanf-ccdf-ak-ne (#794) | 72 | 66 | 5 (2 IL, 2 MT, CA WIC bulk) | 1 duplicate carrier (`us-az/statute/...-tanf-ccdf-statutes-az`) |
| tanf-ccdf-nh-wy (#791) | 67 | 66 | 1 (WAC 110-15) | |
| health (#793) | 44 | 40 | 4 (CO, IL, 2 WA) | |
| benefits (#789) | 56 | 52 | 3 (IL, MD, TX re-version) | 1 duplicate carrier (`us-mo/regulation/...-benefits-regulation-mo`) |
| **total** | 390 | 366 | 15 | 9 |

Every selected scope has a coverage file with `complete: true`, 0 missing, 0 extra, 0 duplicate citations (script over
all 1,445 files). No citation path appears in two selected scopes (script over 402,143 paths).

## Consolidations

`scripts/consolidate_release_scopes.py`, the mechanism of the 2026-09-11 and 2026-09-14 passes: one immutable successor
from ordered sources, released scope first, byte-identical body-less container rows folded, conflicting rows refused
unless a carrier is named. Released scopes and the agents' extractions stay untouched. Run from the release worktree.
Three builds were redone during the pass (MT, MA and the CA WIC name); the earlier outputs were never signed or
shared and were moved out of the corpus root to the session scratch directory.

```bash
B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
C="uv run --extra dev python scripts/consolidate_release_scopes.py --base $B"

# K1 us/regulation: 26 CFR part 1 container
$C --jurisdiction us --document-class regulation \
  --source-version 2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated \
  --source-version 2026-10-06-w6-federal-ecfr-closure-title-26-part-1 \
  --target-version 2026-07-24-1401-coordination-repair-title-26-part-1-r2026-09-13-closure-sections-consolidated-r2026-10-07-w6-1-414-consolidated

# K2 us-co/statute: root container (the two rows differ only in identifiers and source fields; keep the released row)
$C --jurisdiction us-co --document-class statute \
  --source-version 2026-07-19-rulespec-us-co-title-39-consolidated \
  --source-version 2026-10-06-w6-health-statute-co-crs2025 \
  --prefer-duplicate-carrier us-co/statute=2026-07-19-rulespec-us-co-title-39-consolidated \
  --target-version 2026-07-19-rulespec-us-co-title-39-consolidated-r2026-10-07-w6-title-10-consolidated

# K3 us-hi/statute: volume-04 container (HRS chapter 346, released in the July foundation cuts)
$C --jurisdiction us-hi --document-class statute \
  --source-version 2026-07-16-pit-east-us-hi-volume-04-chapter-235 \
  --source-version 2026-07-03-hi-hrs-us-hi-chapter-346 \
  --target-version 2026-07-16-pit-east-us-hi-volume-04-chapter-235-r2026-10-07-chapter-346-consolidated

# K4 us-il/regulation: root, title-089, chapter-iv, subchapter-b containers
$C --jurisdiction us-il --document-class regulation \
  --source-version 2026-09-14-income-tax-regulations-title-086-part-00100 \
  --source-version 2026-10-06-w6-tanf-ccdf-rules-il-title-023-part-02060 \
  --source-version 2026-10-06-w6-tanf-ccdf-rules-il-title-089-part-00050-00112 \
  --source-version 2026-10-06-w6-benefits-ssi-aabd-il-title-089-part-00113 \
  --source-version 2026-10-06-w6-health-regulation-il-title-089-part-00120 \
  --target-version 2026-09-14-income-tax-regulations-title-086-part-00100-r2026-10-07-w6-title-023-089-consolidated

# K5 us-md/regulation: root, title-07, subtitle-03 containers (COMAR 07.03.17)
$C --jurisdiction us-md --document-class regulation \
  --source-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-09-14-chapter-03-title-03-subtitle-04-consolidated \
  --source-version 2026-10-06-w6-benefits-snap-comar-md-publication-2026-10-05-title-07-subtitle-03-chapter-17 \
  --target-version 2026-09-10-ssi-state-supplement-publication-2026-09-09-title-07-subtitle-03-chapters-06-07-r2026-10-07-chapters-03-17-title-03-subtitle-04-consolidated

# K6 us-mt/regulation: root and title-37 containers; ARM 37.78 without rule 37.78.420 (see Decisions for the owner)
S78=2026-10-06-w6-tanf-ccdf-rules-mt-title-37-section-37-78
ARGS=(); for p in $(jq -r .citation_path $B/provisions/us-mt/regulation/$S78.jsonl \
    | grep -vx us-mt/regulation/title-37/chapter-37-78/subchapter-37-78-4/rule-37-78-420); do
  ARGS+=(--include-citation-from "$S78=$p"); done
$C --jurisdiction us-mt --document-class regulation \
  --source-version 2026-09-14-income-tax-regulations-title-42-section-42-15 \
  --source-version $S78 --source-version 2026-10-06-w6-tanf-ccdf-rules-mt-title-37-section-37-80 "${ARGS[@]}" \
  --target-version 2026-09-14-income-tax-regulations-title-42-section-42-15-r2026-10-07-w6-37-78-37-80-sans-420-consolidated

# K7 us-oh/regulation: root container (wave-5 OAC 5180:6-1)
$C --jurisdiction us-oh --document-class regulation \
  --source-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-r2026-09-14-5703-7-consolidated \
  --source-version 2026-09-15-ccdf-subsidy-rules-agency-5180-6-chapter-5180-6-1 \
  --target-version 2026-07-16-agency-5101-4-r2026-09-11-5101-1-5122-36-r2026-09-14-5703-7-consolidated-r2026-10-07-5180-6-1-consolidated

# K8 us-or/regulation: root container (wave-5 OAR 414-175)
$C --jurisdiction us-or --document-class regulation \
  --source-version 2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated \
  --source-version 2026-09-15-ccdf-subsidy-rules-chapter-414-division-175 \
  --target-version 2026-09-10-tanf-state-policy-manual-chapter-461-r2026-09-14-150-316-consolidated-r2026-10-07-414-175-consolidated

# K9 us-or/statute: title-29 container (ORS 316 + ORS 315); ORS 315 carries 315.264/.266 in place of the recovery rows
N315=2026-10-06-w6-income-tax-statute-or-us-or-chapter-315
$C --jurisdiction us-or --document-class statute \
  --source-version 2026-07-16-pit-west-us-or-chapter-316 --source-version 2026-07-13-recovery --source-version $N315 \
  --drop-shadowed-block 2026-07-13-recovery=$N315 \
  --prefer-duplicate-carrier us-or/statute/315.264=$N315 --prefer-duplicate-carrier us-or/statute/315.266=$N315 \
  --target-version 2026-07-16-pit-west-us-or-chapter-316-r2026-10-07-recovery-316-085-w6-chapter-315-consolidated

# K10 us-wa/regulation: root, 388 and 182 containers (388-400, -424, -470 released in the July foundation cuts)
$C --jurisdiction us-wa --document-class regulation \
  --source-version 2026-06-25-388-450-r2026-07-15-self-contained \
  --source-version 2026-06-25-388-400 --source-version 2026-06-25-388-424 --source-version 2026-06-25-388-470 \
  --source-version 2026-10-06-w6-ccdf-rules-wa-110-15 \
  --source-version 2026-10-06-w6-health-regulation-wa-182-505 --source-version 2026-10-06-w6-health-regulation-wa-182-512 \
  --target-version 2026-06-25-388-450-r2026-07-15-self-contained-r2026-10-07-388-400-424-470-w6-110-15-182-consolidated

# K11 us-ma/statute: signed s. 2 scope + wave-5 c. 62 without the 12 sections the released recovery scope serves
S2=2026-09-23-ma-mgl-chapter-62-us-ma-part-i-title-ix-chapter-62-sections-2
CH=2026-09-15-income-tax-chapter-us-ma-part-i-title-ix-chapter-62
ARGS=(); for p in $(jq -r .citation_path $B/provisions/us-ma/statute/$CH.jsonl | grep -vxF -f <(
    jq -r .citation_path $B/provisions/us-ma/statute/2026-07-13-recovery.jsonl | grep -v /block-)); do
  ARGS+=(--include-citation-from "$CH=$p"); done
$C --jurisdiction us-ma --document-class statute --source-version $S2 --source-version $CH "${ARGS[@]}" \
  --prefer-duplicate-carrier us-ma/statute/62/2=$S2 \
  --target-version $S2-r2026-10-07-chapter-62-without-recovery-sections-consolidated

# K12 us-in/statute: the recovery scope without IC 12-15-32-6 and -6.5 (carried by the w6 Indiana Code Title 12 scope)
R=2026-07-13-recovery
$C --jurisdiction us-in --document-class statute --source-version $R \
  $(for s in 6-3-2-10 6-3-2-22 6-3-2-28 6-3-2-4 6-3-2-6 6-3-3-12 6-3-3-9 6-3.1-21-6; do
      printf -- '--include-citation-from %s=us-in/statute/%s ' $R $s; done) \
  --target-version $R-r2026-10-07-without-12-15-32-consolidated

# K13 us-ca/statute: the w6 WIC bulk scope without the eight sections released section scopes serve
uv run --extra dev python - <<'PY'
import sys; from pathlib import Path
sys.path.insert(0, "scripts")
from consolidate_release_scopes import consolidate_release_scopes
from axiom_corpus.corpus.io import load_provisions
base = Path("/Users/pavelmakarchuk/axiom-corpus/data/corpus")
src = "2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-WIC"
released = {f"us-ca/statute/wic/{s}" for s in
            ("11450", "11450.12", "11451.5", "11452", "11452.018", "12200", "18901.3", "18901.5")}
rows = load_provisions(base / "provisions/us-ca/statute" / f"{src}.jsonl")
assert not any(r.parent_citation_path in released for r in rows)
consolidate_release_scopes(
    base=base, jurisdiction="us-ca", document_class="statute", source_versions=(src,),
    target_version="2026-10-06-w6-tanf-ccdf-statutes-ca-us-ca-title-wic-r2026-10-07-without-released-sections-consolidated",
    included_citations_by_version={src: frozenset(r.citation_path for r in rows) - released})
PY

# K14 us-tx/statute: lowercase re-version (selector scope names must match ^[a-z0-9][a-z0-9._-]*$)
$C --jurisdiction us-tx --document-class statute \
  --source-version 2026-10-06-w6-benefits-ssi-statute-us-tx-title-HR \
  --target-version 2026-10-06-w6-benefits-ssi-statute-us-tx-title-hr-r2026-10-07-consolidated
```

| Successor (jurisdiction/class, version suffix) | Sources (rows) | Rows | Folded or left out |
| --- | --- | ---: | --- |
| `us/regulation ...-r2026-10-07-w6-1-414-consolidated` | 346 released + 29 | 374 | `us/regulation/26/1` |
| `us-co/statute ...-r2026-10-07-w6-title-10-consolidated` | 1,137 released + 313 | 1,449 | `us-co/statute` (released row kept) |
| `us-hi/statute ...-r2026-10-07-chapter-346-consolidated` | 156 released + 280 released (July) | 435 | `us-hi/statute/volume-04` |
| `us-il/regulation ...-r2026-10-07-w6-title-023-089-consolidated` | 200 released + 86 + 135 + 97 + 145 | 655 | 8: root (4 copies), `title-089` (2), `chapter-iv`, `subchapter-b` |
| `us-md/regulation ...-r2026-10-07-chapters-03-17-title-03-subtitle-04-consolidated` | 166 released + 66 | 229 | root, `title-07`, `title-07/subtitle-03` |
| `us-mt/regulation ...-r2026-10-07-w6-37-78-37-80-sans-420-consolidated` | 62 released + 53 + 25 | 136 | root (2 copies), `title-37`; rule 37.78.420 left out |
| `us-oh/regulation ...-r2026-10-07-5180-6-1-consolidated` | 185 released + 15 | 199 | root |
| `us-or/regulation ...-r2026-10-07-414-175-consolidated` | 718 released + 44 | 761 | root |
| `us-or/statute ...-r2026-10-07-recovery-316-085-w6-chapter-315-consolidated` | 502 released + 6 released + 214 | 717 | `title-29`; recovery 315.264, 315.266 and their `block-1` rows replaced |
| `us-wa/regulation ...-r2026-10-07-388-400-424-470-w6-110-15-182-consolidated` | 45 released + 13 + 13 + 10 (July) + 117 + 14 + 36 | 238 | 10: root (6 copies), `388` (3), `182` |
| `us-ma/statute ...-r2026-10-07-chapter-62-without-recovery-sections-consolidated` | 4 (signed 2026-09-23) + 70 | 58 | 3 containers; c. 62 ss. 3, 4, 6, 6L, 10A, 11A, 14, 16, 42, 54, 62, 64 left out; s. 2 from the signed scope |
| `us-in/statute 2026-07-13-recovery-r2026-10-07-without-12-15-32-consolidated` | 10 released | 8 | IC 12-15-32-6, -6.5 left out |
| `us-ca/statute ...-title-wic-r2026-10-07-without-released-sections-consolidated` | 7,987 | 7,979 | WIC 11450, 11450.12, 11451.5, 11452, 11452.018, 12200, 18901.3, 18901.5 left out (leaves; no child row) |
| `us-tx/statute ...-title-hr-r2026-10-07-consolidated` | 1,806 | 1,806 | none (re-version only) |

Checked after writing (script over the JSONL, `bytecheck`): every released source row is in its successor byte-equal
(body and every field except `id`, `parent_id`, `version` and the rewritten `source_path`), except the four rows of
`us-or/statute/2026-07-13-recovery` replaced by design. Every other source row is byte-equal or a folded body-less
container. The three non-container replacements:

- ORS 315.264 and 315.266: the recovery roots are body-less, and each `block-1` row holds the whole ORS chapter 315
  page (57,277 words); every word of the new section text is in it. Served text: the section only.
- IC 12-15-32-6 and -6.5 (K12 plus the Title 12 scope): the recovery rows are the same words behind an
  "Indiana Code IC 12-15-32-6 IC 12-15-32-6 ..." page heading; Title 12 adds the history line.
- M.G.L. c. 62 s. 2: the wave-5 row and the signed 2026-09-23 row are identical after whitespace and the leading
  "Section 2." label; the 2026-09-23 row keeps the official line breaks, so it is the carrier.

The successors' `sources/` directories hold every input's files (`sources/<jur>/<class>/<target>/<source-version>/...`);
for K11, K12 and K13 that includes the files of the left-out rows. `validate-release` accepts this.

## Swaps (released scope out, other scope in)

| Jurisdiction / class | Out | In | Cited paths |
| --- | --- | --- | --- |
| us-ca / statute | `2026-06-25-ca-wic-calworks-...-wic-11452.018` (5) | `...-r2026-09-24-preserve-tables` | the 2026-09-24 release's swap |
| us-ca / statute | `2026-09-14-income-tax-chapter-us-ca-sections-4e26e6efabc3f0c7` (1,029) | `...-r2026-09-24-preserve-tables` | the 2026-09-24 release's swap |
| us-in / manual | `2026-09-14-liheap-benefit-matrix` (112) | `2026-10-06-w6-benefits-manual-in` (122) | all 112 paths carried; bodies are the PY2026 edition (by design, benefits note) |
| us-wi / statute | `2026-07-16-pit-west-chapter-71` (116) | `2026-09-23-income-tax-subunits-chapter-71` (5,034, signed) | all 116 carried, row-equal |
| 12 scopes | the released consolidation inputs above | their successors | carried except the two OR block rows |

Released citation paths that no selected scope carries (script over all 402,143 paths): two,
`us-or/statute/315.264/block-1` and `us-or/statute/315.266/block-1` (the chapter-page rows above). rulespec-us
`origin/main` a9dc38fb0 cites the section roots, not these rows.

## Re-selected signed scopes (in no union selector, cited ALREADY-HELD)

The agents counted locked scopes as held (the controller's mid-run ruling), so their decisions cite 21 signed scopes on
`main` that no union selector carries. Re-selected where the cited path is in no other selected scope (each `complete:
true`, signed, 0 path collisions): 16 directly, 5 through K3, K10 and K11. Rows they serve, by scope:

- 2026-09-23 (11): `us-va/regulation/...-va-22vac40-601-snap` (7), `us-wi/statute/...-income-tax-subunits-chapter-71`
  (8, swap above), `us-ca/guidance/...-ca-cdss-acl-06-31` (2), `us-ma/guidance/...-ma-dta-policy-online-snap-child-support`
  (2), `us/statute/...-tax-statute-policybench-title-26` (2), `us-ny/form/...-ny-it-214-ty2025` (2),
  `us-wi/form/...-wi-schedule-sb-2025` (2), `us-de/rulemaking/...-de-register-13-de-reg-1550` (1),
  `us-il/manual/...-il-dhs-mr-23-22` (1), `us-ca/form/...-ca-2025-ftb-3514` (1), `us-ma/guidance/...-ma-dor-tir-02-21` (1).
- July (5): `us-mi/statute/2026-07-16-mi-fip-statutory-authority` (1), `us-dc/manual/2026-07-19-dc-child-care-subsidy` (1),
  `us-tx/manual/2026-07-13-tx-twh-c120` (1), `us/form/2026-07-05-cms-chip-children-coverage-map` (1),
  `us-de/regulation/2026-07-03-de-dssm-13000` (1); the last three are among the "candidates for the next selector" of
  `docs/coverage/needs-closure-2026-09-14/README.md`.
- Through successors: `us-wa/regulation/2026-06-25-388-400`, `-424`, `-470` (6 rows), `us-hi/statute/2026-07-03-hi-hrs-us-hi-chapter-346`
  (1), `us-ma/statute/2026-09-23-...-sections-2` (2).

Not re-selected: `us/rulemaking/2026-06-03-cms-2454-ifc-types-rule-term-cms-2454-ifc-limit-1` (locked but never
signed; 2 federal rows), and the cited July scopes whose cited paths a selected successor already carries.

## Wave-5 scopes

Selected (cited ALREADY-HELD by 58 wave-6 rows; all `complete: true`): 18 directly and 3 through K7, K8 and K11.

- From #716 (tax): `us/form/2026-09-15-irs-forms-ty2025`; `2026-09-15-income-tax-forms-ty2025` of us-az, us-ca, us-ct,
  us-mi, us-mo, us-nd, us-oh, us-or, us-sc, us-va, us-wi, us-wv; `us-ma/statute/2026-09-15-income-tax-chapter-...-chapter-62` (K11).
- From #717 (tanf-ccdf): `2026-09-15-ccdf-subsidy-rules` of us-id, us-me, us-ok, us-ri (regulation) and us-sc (manual);
  `us-oh/regulation/...-agency-5180-6-chapter-5180-6-1` (K7); `us-or/regulation/...-chapter-414-division-175` (K8).

Recommended follow-up, not selected: the other 98 wave-5 scopes on disk (4,099 rows, every one `complete: true`). By
family: 51 `medicaid-magi-verification-plan` (#714), 11 `income-tax-forms-ty2025` (HI, IL, KS, LA, MA, ME, MN, NC, NE,
NY, RI; #716), 7 `medicaid-1115-stc` (#714), 6 `ccdf-subsidy-rules` (IN, KY, NE, NM, SD, VT; #717), 4
`ccdf-rate-schedules` (#717), 2 `medicaid-income-table-2026`, 2 `chip-income-premium-table-2026`, the WY eligibility
manual closure (#714), 2 `ssi-state-supplement-rules`, LIHEAP model plan and AR LIHEAP manual, the two Medicare IOM
manuals, POMS SI 00529, 20 CFR 416 appendix K (#718), the IRS rev. proc. guidance and 26 CFR 301 closure (#716), the WIC
food-package FR rule, MA SNAP charts, TN WIC rule (#715), and `us-nc/statute/2026-09-15-income-tax-chapter` (#716).
Collisions against this selection: 94 none; `us/rulemaking/...-wic-federal-register-2024-07437-...` shares the
identical container `us/rulemaking/federal-register` with the released tariff rulemaking union (fold);
`us-mn/manual/2026-09-15-medicaid-income-table-2026` shares 25 paths with `us-mn/manual/2026-09-10-medicaid-state-eligibility-manual`;
`us-nc/statute/2026-09-15-income-tax-chapter` shares 4 section roots with `2026-08-03-nc-income-tax-current-union`
(body-less in the new scope; the wave-5 note's NC swap decision); `us-wi/statute/2026-09-15-ssi-state-supplement-rules`
shares `us-wi/statute/49.77` with the selected chapter 49 scope (drop it: the chapter carries the section).

## On disk, not selected

- The six superseded tax-mn-oh first-run scopes (ny statute, nj guidance, oh forms, ny forms, mt statute, nm statute).
- `us-az/statute/2026-10-06-w6-tanf-ccdf-statutes-az`: the same azleg.gov pages (same SHA-256) at the same paths as the
  selected `us-az/statute/2026-10-06-w6-benefits-snap-statute-us-az-title-46`.
- `us-mo/regulation/2026-10-06-w6-benefits-regulation-mo`: the same 13 CSR 40-2 PDF, page-level; the section-level
  `us-mo/regulation/2026-10-06-w6-tanf-ccdf-rules-mo` is selected. Benefits decisions rows 156-159 are re-pointed to its
  section paths (separate commit on this branch).
- `us/statute/2026-10-06-w6-federal-usc-medicaid-sections-title-42`: held out, see Decisions for the owner.
- The consolidation inputs: 15 wave-6 scopes, 3 wave-5 scopes, the 5 re-selected July and 2026-09-23 inputs, and the
  12 released scopes they replace. The original CA WIC and TX HR scopes cannot be selected under their own names
  (uppercase `WIC`, `HR`: the selector grammar rejects them); the `california-codes-bulk` and `texas-tcas` adapters
  put the code abbreviation into the version suffix unlowered.
- The tax-mn-oh decisions row for the MN 2026 inflation-adjusted amounts named the per-bracket scope that wave 4 took
  out of the union selectors; it is re-pointed to `us-mn/guidance/2026-09-14-ty2026-indexed-amounts`, the carrier its
  own note recommends (same commit). The decisions' `scope_version` column otherwise names the extraction run; joins
  use `citation_path`, and the selector is the release truth.

PRESENT and ALREADY-HELD rows whose path this selection does not carry (script over all 2,719 such rows): 9.
federal 284/286/289/292 (the held-out 1396a/b/d/p roots), federal 37/38 (the unsigned CMS-2454 FR scope), tax-al-hi
308/309 (D.C. Code 47-1806.15 and .17, PR #753), tax-ia-mi 27 (`us-ia/regulation/iac/701`, a virtual container: the
bundle collector should count a document whose root is no node but whose children are, as the integration notes say).

## Dependencies on open PRs

- **#716, #717** (wave 5): the 21 wave-5 scopes selected here were extracted on those branches; their manifests and
  run notes must be on the signing branch (merge them or their branches first) so the signed manifests name a rebuild
  command that exists in the tree.
- **#753** (D.C. title 47): 2 tax-al-hi rows hold their sections in its `us-dc/statute/2026-09-26-codified-title-47`.
- **#761** (ARM 37.78.420 chrome-free recovery successor): its source JSON is byte-identical to the one the w6 ARM 37.78
  scope used. This cut keeps the released recovery row and leaves 37.78.420 out of K6; whichever carrier the owner
  picks, only one can be selected.
- **#752** (CA LegInfo concurrent versions, WIC 11450 and 11451.5 among them): bears on the eight CA WIC sections this
  cut keeps from the released section scopes.
- **#763** (SNAP child-support cited sources): three of its scopes hold the same bytes as wave-6 sources selected here
  (COMAR 07.03.17 XML, in K5; the Louisiana Register April 2003 PDF, `us-la/rulemaking/...-w6-benefits-rulemaking-la`;
  the LAC title 67 DOCX, `us-la/regulation/...-w6-tanf-ccdf-rules-la`). Selecting both later duplicates the documents
  (and, for COMAR, the MD containers): pick one carrier per document when #763 is cut.
- Selector-cutting PRs (names claimed, none reused here): #729 `us-rulespec-2026-09-22-hts-full-schedule-union` (wave4-r2
  + the HTS 2026 rev. 15 full schedule in place of `us/statute/2026-08-09-rulespec-hts`, + a legacy-aluminum
  self-contained scope); #762 `us-rulespec-2026-09-27-ctc-public-laws-union` (wave4-r2 + `us/statute/2026-09-27-ctc-history-public-laws`)
  and `us-ctc-history-2026-09-27-rp-118-209` (publish-only); #772 `us-rulespec-2026-09-29-election-uocava-nvra`
  (small lineage + title 52); #627 `us-rulespec-2026-08-29-usc-469-union` (small lineage, title 26 with 469); #746
  `us-rulespec-2026-09-24-al-ty2025-income-tax-union` (small lineage; no scope that wave4-r2 lacks); #767 (il) and
  #751 (ug) are not US. None of their new scopes is in this cut. Every one of them carries `us/statute`, which this cut
  also carries (five new scopes: four wave-6 federal statute scopes and the PolicyBench title 26 scope): serving is last-activation-wins per pair, so whichever is activated
  second must carry the other's `us/statute` scopes. #772 and #627 extend the small lineage and would also take
  `us/statute` back to that lineage's membership. Rebase them onto this selector (or add their scopes here) before
  either is activated.
- Other in-flight US scopes in no conflict with this selection by path or source hash: #754 (ME title 36 subunits),
  #760 (SC 12-6-520), #771 (title 52), #773 (NYC admin code), #778 (KS LIEAP).

## Decisions for the owner

1. **42 U.S.C. 1396a, 1396b, 1396d, 1396p** (`us/statute/2026-10-06-w6-federal-usc-medicaid-sections-title-42`, 2,356 rows,
   release point 119-103): it shares 361 paths with released scopes. 258 shared with `2026-09-13-medicaid-statute-closure-title-42`
   and 89 of 91 shared with `2026-06-26-medicaid-title-42-...-r2026-07-17-dedup` have equal bodies. The text differs at
   14: `1396a/a/10` and `1396d/a` (the released 2025-12-08 text against 2026-09-02) and the 12 rows of
   `2026-06-29-pl-119-21-medicaid-community-engagement-r2026-07-15-self-contained` (1396a(xx) as quoted in P.L. 119-21
   against the codified text). Held out; 4 federal PRESENT rows (the section roots) wait on it. Options: (a) serve
   119-103 throughout: successors of the three released scopes without the 361 shared paths (the closure and dedup
   scopes keep 566 and 21 other rows; the P.L. 119-21 scope is all shared) plus the whole-section scope; (b) keep the
   released text: the whole-section scope without the 361 paths (subsections of one section would then mix currency
   dates); (c) leave it out.
2. **ARM 37.78.420** (MT TANF assistance standards): the released `us-mt/regulation/2026-07-13-recovery` row is the 2011
   version (page chrome included); the w6 ARM 37.78 row, and the source #761 uses, is the rule as amended by MAR Notice
   No. 2026-529 (effective 2026-09-26, new benefit tables). rulespec-us `origin/main` a9dc38fb0 cites the path 11 times.
   This cut keeps the released row. To serve the 2026 text: rebuild K6 without the include filter and drop the
   recovery scope, or select #761's successor.
3. **M.G.L. c. 62 and the Massachusetts recovery scope**: the wave-5 tax note says swap the recovery scope for the
   chapter, but that loses 24 released `block-N` paths, and rulespec-us `origin/main` a9dc38fb0 cites three of them
   (`us-ma/statute/62/3/block-2`, `62/4/block-2`, `62/6/block-2`, in `us-ma/policies/income_tax/2026_full_year_resident_source_hold.yaml`
   and `pilot_liability_pipeline.yaml`). This cut keeps the recovery scope (its 12 sections stay served from it) and
   takes the other chapter sections through K11. The chapter text of the 12 sections equals the recovery block text
   (every word of each section is in its blocks). To swap: re-point those rulespec-us citations to the section roots,
   rebuild K11 without the exclusion and drop the recovery scope.
4. **California WIC, eight sections** (11450, 11450.12, 11451.5, 11452, 11452.018, 12200, 18901.3, 18901.5): kept from the
   released section scopes (rulespec-us `origin/main` a9dc38fb0 cites all eight). The bulk text differs: no table-cell preservation, the
   history note as heading, and for 11451.5 another version of the section (released: "Except as provided in
   subdivision (c), ..."; bulk: the Stats. 2019 text). Relates to #752.
5. **CMS-2454 FR document scope**: locked on `main` but never signed and never selected; signing and selecting it
   would serve federal rows 37-38 (the regulation amendments are already served).
6. Carried from the run notes: the ilga.gov browser user-agent fallback (6 tax-ia-mi OUTREACH rows; the health agent
   reached the same repository on ftp.ilga.gov); whether bill-status pages belong in the statute class (tax-ia-mi);
   the two federal container references, `us/statute/26/subtitle-A` and `us/statute/42/chapter-7` (SKIPPED).

## Ratchets

Counted over the tree the signing commit makes (the 1,906 locked provisions files on `main`, read from the corpus root
or their git blobs, plus the 398 new scopes; unique paths): the selection adds 71,616 paths that no locked scope has.

| Family | Baseline (= `main` now) | Added | After | Raise |
| --- | ---: | ---: | ---: | ---: |
| `block_n` | 75,916 | 8,930 | 84,846 | +8,930 |
| `page_n` | 150,654 | 25,416 | 176,070 | +25,416 |
| `uppercase_segments` | 16,281 | 2,480 | 18,761 | +2,480 |
| `space_segments` | 196 | 111 | 307 | +111 (all `us-nh/regulation/...-w6-tanf-ccdf-regulation-nh`, He-C 6900 labels) |
| `endash_segments`, `truncated_segments`, `collection_roots` | 1,652 / 53 / 10 | 0 | unchanged | none |

The reviewer must approve the raise of `block_n`, `page_n`, `uppercase_segments` and `space_segments` in
`schema/citation-path.v1.json` in the signing PR (`scripts/validate_citation_paths.py --update-baselines` over a
fully fetched tree, then review the diff); `test_citation_path_grammar` fails without it.

## Checks

- Coverage: 1,445 of 1,445 `complete: true`, no missing, extra or duplicate citations.
- No citation path in two selected scopes: 402,143 paths, 0 duplicates.
- Successors: every released source row byte-equal except the four OR recovery rows replaced by design (above).
- Citation-path grammar: `uv run --extra dev python scripts/validate_citation_paths.py --provisions <tree of the 398 new
  provisions files>`: 75,572 records, 75,572 unique paths, `RESULT: OK` (0 pattern failures, 0 jurisdiction or class
  mismatches, no identity drift).
- `uv run --extra dev axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus
  --release docs/ingest-runs/2026-10-07-us-rulespec-w6-bundle-gaps-union.selector.json --ignore-r2-missing --max-issues 1000`:
  `ok: true`, `scope_count: 1445`, `error_count: 0`, `warning_count: 562` (57 s). 546 are the pre-existing ones of the
  wave-4 note (541 `missing_parent_id` in `us-ca/regulation/2026-07-13-recovery`, 5 `unsectioned_document_body`). 16 are
  new and advisory: 4 `empty_provision_text` (`us-al/statute/title-16/chapter-5a/article-1` to `-4` of the ALISON Title
  16 scope: no body, no heading) and 12 `unsectioned_document_body` on single-block w6 forms (AZ 2, IA 2, IL 5, MN 1,
  NY 1, UT 1). No `duplicate_release_citation`.
- `scripts/audit_release_scope_self_containment.py --release <draft> --base <corpus root>`: `residual_count: 0` over
  1,445 scopes.
- `scripts/audit_us_release_publishability.py --repo . --base <corpus root> --release-ref WORKTREE --release-path <draft>`
  (read-only, no `--repair-derived`): `artifact_lacking_count: 0`, `manifest_lacking_count: 398`, exit 2. The 398 are
  exactly the unsigned scopes the signer adds (366 wave-6, 18 wave-5, 14 successors); the other 1,047 have signed manifests.
- `scripts/check_release_gate.py`: not runnable before signing (it needs `--release-object` and `--content-sha` of a
  signed release object). `scripts/publish_corpus.py --dry-run`: not run; it accepts only a committed
  `manifests/releases/<name>.json` whose artifacts are locked at `HEAD`, which is the signing step.
- Source hashes: no source file of a selected new scope is byte-identical to a source of another selected scope or of a
  locked scope, apart from shared index and bulk files (ALISON pages, the Indiana Code and U.S. Code release zips,
  JCAR/COMAR/RI/WI index pages, and the ORS chapter 315 page that the OR recovery scope also retained) and the two
  duplicate carriers above. Three sources match #763 (above).
- Branch merge: the nine branches merge onto `main` with one conflict, in `_extract_html_blocks` of
  `src/axiom_corpus/corpus/documents.py`, between federal's `html_parser` option and tax-ia-mi's
  `html_keep_default_drop_selectors`; both are additive and are combined. Impact analysis: not run (the GitNexus MCP
  tools are not available in this session); `_extract_html_blocks` is the one caller of both helpers. Focused tests
  (`AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev pytest -q tests/test_html_keep_default_drop_selectors.py
  tests/test_corpus_documents.py tests/test_corpus_states.py -k "html or texas or soup or keep or parser"`): 56 passed.
  `ruff check .` passes. `data/certs/globalsign-rsa-ov-ssl-ca-2018.pem` arrives from three branches as one blob
  (619b81c0e; SHA-256 fingerprint B6:76:FF:A3...:4A, valid to 2028-11-21). The queue YAML files merge without
  conflict, and every `status_counts` block equals its rows' `queue_status` counts (tax 102 -> 114 rows, `done` 72 -> 84;
  no recount needed).

## Data-quality follow-ups

- `scripts/sign_release_scopes.sh` predates the lock switch (#774): its step 1 `git add -f`s the scopes' corpus files,
  which `guard-ingested` rejects once lock files exist ("one representation"), and it does not lock. Use the sequence
  below, or update the script to sign with `--lock`.
- The `california-codes-bulk` and `texas-tcas` adapters should lowercase the code abbreviation in the version suffix.
- From the run notes: OH H.B. 96 (9.6 M characters), NM Laws 2023 and other single huge rows to split; GA 560-7-4-.02
  holds rules .03-.05; the May-2026 manifest paths that the w6 agents re-slugged need `path_moves` in the bundle joins.

## What the signer runs next

1. Merge, in order: the nine wave-6 PRs (or this branch), #716 and #717; then cut the release branch from `main`. Place
   the 398 unsigned scopes in that checkout's own `data/corpus` (`--lock` locks the repository's own corpus root), then
   fetch the locked rest:

   ```bash
   B=/Users/pavelmakarchuk/axiom-corpus/data/corpus
   tail -n +2 docs/ingest-runs/2026-10-07-w6-release-unsigned-scopes.tsv | while IFS=$'\t' read -r j c v note; do
     for f in inventory/$j/$c/$v.json provisions/$j/$c/$v.jsonl coverage/$j/$c/$v.json; do
       mkdir -p "data/corpus/$(dirname "$f")" && cp -c "$B/$f" "data/corpus/$f"; done
     mkdir -p "data/corpus/sources/$j/$c" && cp -cR "$B/sources/$j/$c/$v" "data/corpus/sources/$j/$c/"
   done
   uv run axiom-corpus-ingest corpus fetch --release docs/ingest-runs/2026-10-07-us-rulespec-w6-bundle-gaps-union.selector.json
   ```

2. In that shell only, export `AXIOM_CORPUS_INGEST_PRIVATE_KEY` (keychain step) and `AXIOM_CORPUS_INGEST_PUBLIC_KEY`. With a
   clean tracked tree, sign and lock the 398 scopes of
   `docs/ingest-runs/2026-10-07-w6-release-unsigned-scopes.tsv` (the draft's scopes without a signed manifest, each
   with the run note that records its rebuild command):

   ```bash
   tail -n +2 docs/ingest-runs/2026-10-07-w6-release-unsigned-scopes.tsv |
   while IFS=$'\t' read -r j c v note; do
     uv run axiom-corpus-ingest sign-ingest-manifest --jurisdiction "$j" --document-class "$c" --version "$v" \
       --command "rebuild: see $note" --lock --push < /dev/null || break
   done
   git add .axiom/ingest-manifests .axiom/corpus-locks
   git commit -m "Sign and lock the us-rulespec-2026-10-07-w6-bundle-gaps-union scopes"
   ```

3. Raise the four ratchets (above) in `schema/citation-path.v1.json` as a reviewed commit.
4. `cp docs/ingest-runs/2026-10-07-us-rulespec-w6-bundle-gaps-union.selector.json manifests/releases/us-rulespec-2026-10-07-w6-bundle-gaps-union.json`, then
   `uv run axiom-corpus-ingest validate-release --base data/corpus --release manifests/releases/us-rulespec-2026-10-07-w6-bundle-gaps-union.json --ignore-r2-missing`
   and `uv run axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD`; commit the selector and open the PR
   (CI runs the guard and validates the selector).
5. `uv run --extra dev python scripts/publish_corpus.py --release manifests/releases/us-rulespec-2026-10-07-w6-bundle-gaps-union.json --dry-run`,
   then the protected publication and `activate-release.yml` flow (preview the takeover first; see the #729/#762/#772/#627
   note above).

Disk: 3.2 TiB free at the start and the end. The 398 new scopes hold 6,205 files, 3.97 GB, of which the CA WIC bulk zip
is 1.29 GB (one object). The controller also placed 26 locked scopes' files (1,271 files, from git objects, no R2 read)
into the corpus root so that every selected scope is present there.
