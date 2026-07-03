# Subsection-granularity policy — proposal (issue-14)

Status: **PROPOSAL. Recommends, does not decide.** Max ratifies on the PR.
Phase-A item **A6** (`axiom-rebuild-plan-2026-07-02.md`): *"the issue-14
granularity policy decided (subsection paths: encode-at-subsection vs
section-rollup)."* This document analyzes the choice and makes **one**
recommendation with rationale; the decision is recorded when this PR merges.

**TL;DR:** the federal case that motivated issue #14 (`7 CFR 273.9(d)(6)(iii)`
across 7 SNAP specs) has **already been resolved along the section-rollup path**
— a subsection-*path* module (rulespec-us #440) grounded on the section-level
corpus provision `us/regulation/7/273/9`, with the subsection cited in rule
`source` metadata. The corpus was never re-segmented. The recommendation is to
**ratify that as-built pattern as policy** and finish the small us-ma tail the
same way; reserve corpus-level subsection re-segmentation for oracle-justified
`split`s.

Tracking issue: [`axiom-programs#14`](https://github.com/TheAxiomFoundation/axiom-programs/issues/14)
(note: the `axiom-programs` repo is **archived / read-only**, so this proposal
is the live venue; the issue cannot be commented on).
Related: [`schema/citation-path.v1.md`](../schema/citation-path.v1.md),
[`docs/provision-identity.md`](./provision-identity.md), `rulespec-us#523`
(reverse index), `rulespec-us/known-dangling.yaml`, rulespec-us #440
(the module that resolved the federal case).

---

## 1. The problem, precisely

Seven state SNAP program specs, plus three extra `us-ma` state-scope entries,
declared scope entries at a **finer granularity than what was encoded or
ingested** when issue #14 was filed, so the programs could not compose. The
federal entry has since been resolved (§1 below); three `us-ma` entries remain.

The canonical example from issue #14:

```
regulations/7-cfr/273/9/d/6/iii     <- referenced by 7 SNAP specs
```

When issue #14 was filed (2026-06-09) this was dangling on both sides: no
subsection module, and no subsection corpus provision.

**The federal case has since been resolved — and it was resolved the way this
proposal recommends.** Verified against `rulespec-us@main` on 2026-07-03:

- The module `us/regulations/7-cfr/273/9/d/6/iii.yaml` **now exists** (added in
  rulespec-us **#440** "Add SNAP utility allowance rule", 2026-06-25 — after #14
  was filed). Its module path is `regulations/7-cfr/273/9/d/6/iii`, which **is
  exactly the scope entry the 7 specs reference**, so the import resolves.
- That module grounds on the **section-level** corpus provision:
  `source_verification.corpus_citation_path: us/regulation/7/273/9`. The corpus
  was **not** re-segmented — it still carries 7 CFR 273.9 as a single provision
  (`us/regulation/7/273/9`; exactly one corpus path contains `273/9`, stopping
  at the section).
- The subsection precision lives as **rule-level source metadata** inside the
  module: its rules cite `source: 7 CFR 273.9(d)(6)(iii)(D)(3)` etc. That is the
  "subpath anchor" pattern, already in production.
- `rulespec-us/known-dangling.yaml` **no longer lists the federal `273/9`
  entry** — only the two us-ma entries remain.

In other words, the fine-grained *module* path carries the subsection identity
while the *corpus provision* it grounds on stays at the section. **This is
Option B (section-rollup) as-built.** The recommendation below is therefore
largely a request to *ratify the pattern the team already converged on* and
apply it to the us-ma tail, not to introduce something new.

### 1.1 The remaining dangling set (from `known-dangling.yaml`, current)

| scope entry | scope | status | what exists instead |
|---|---|---|---|
| `regulations/7-cfr/273/9/d/6/iii` | federal | **resolved** (module #440 grounds on section `us/regulation/7/273/9`) | — |
| `regulations/106-cmr/364/945/block-1` | state (us-ma) | dangling | nothing under `364/945*` |
| `regulations/106-cmr/365/180/A` | state (us-ma) | dangling | `365/180/block-1.yaml` — **`A` → `block-1` naming drift** |
| `policies/dta/snap/fy-2026-cola/heating-cooling-standard-utility-allowance` | state (us-ma) | dangling | no `policies/` tree at all |

Two of the remaining us-ma entries (`365/180/A`, the DTA SUA policy) are the
*program-side face of the corpus identity drift* documented in
`provision-identity.md` §3 — the same `365/180/A` vs `365/180/block-1` mismatch
appears there as a stored provision UUID that no longer derives from its path.

### 1.2 Two distinct sub-problems hide here

1. **Subsection-depth encoding** (`273.9(d)(6)(iii)`): a rule about the
   homeless-shelter / utility-allowance deduction that lives inside a subsection.
   The corpus never segmented below the section — and it did not need to: the
   rule is now encoded as a subsection-*path* module (#440) grounded on the
   section-level corpus provision. The open question is purely **policy**: is
   that (module fine-grained, corpus at the section) the right standing pattern,
   or should the corpus itself be re-segmented to the subsection?
2. **Naming drift** (`365/180/A` ↔ `365/180/block-1`, `block-1` vs missing
   `364/945`, `policies/` never promoted): the spec references a *label* that
   was re-slugged or never generated. This is not a granularity question — it is
   a rename/promotion question, resolved by the path-mapping events
   (`provision-identity.md` §4) and by promoting the missing modules.

The **policy** decision below is about sub-problem (1) — and the federal case
already answers it in the section-rollup direction. Sub-problem (2) is tracked
but is mechanical clean-up under the identity contract, not a fork in the road.

## 2. The two options

### Option A — encode-at-subsection

Segment the corpus and rules down to the referenced subsection. Concretely:

1. **Corpus**: re-segment `us/regulation/7/273/9` into its subsection tree so
   `us/regulation/7/273/9/d/6/iii` exists as its own provision (and, to be
   consistent, the sibling subsections too). This mints new provision UUIDs.
2. **rulespec-us**: **re-ground** the existing module
   `us/regulations/7-cfr/273/9/d/6/iii.yaml` (from #440) off the section corpus
   provision and onto the new subsection provision, and re-pass its gates.
3. **Program specs**: unchanged (they already point at the subsection module
   path).

### Option B — section-rollup (with subpath anchor)

Keep section granularity as the unit of encoding. Concretely:

1. **Corpus**: unchanged — `us/regulation/7/273/9` stays a single provision.
2. **rulespec-us**: the homeless-shelter-deduction content lives in the
   **section** module `us/regulations/7-cfr/273/9.yaml` (the "income-eligibility
   backbone" the issue references), which grounds on `us/regulation/7/273/9`.
3. **Program specs**: change the scope entry from
   `regulations/7-cfr/273/9/d/6/iii` to the **section** `regulations/7-cfr/273/9`,
   plus a **subpath anchor** naming the subsection within it (e.g. an
   `anchor: d/6/iii` alongside the section reference) so the citation is not
   lost — it becomes metadata on the section reference rather than a path
   segment.

## 3. Cost analysis — what each option invalidates

Costs are grounded in the reverse index shipped by `rulespec-us#523`
(`.axiom/index/provisions_to_rules.json`: **2,609 provisions · 3,021 edges ·
3,020 modules**), which maps each corpus citation path to the modules that
depend on it.

### 3.1 What Option A invalidates

> **Live-index finding (updates issue #14).** The reverse index at
> `rulespec-us#523` already contains `us/regulation/7/273/9` with **2
> dependent modules**: `us/regulations/7-cfr/273/9.yaml` (the section module)
> **and `us/regulations/7-cfr/273/9/d/6/iii.yaml`** (a subsection-depth module,
> grounded via `module` + `proof_atom`). So since issue #14 was filed
> (2026-06-09, when `git log --all -- "273/9/d*"` was empty), a subsection
> module **was** created — and it grounds on the **section-level** corpus
> provision, `corpus_citation_path: us/regulation/7/273/9`. That is already the
> Option-B shape on the corpus side (fine-grained *module*, section-grained
> *corpus provision*, subsection identity carried in the module path). The
> corpus was never re-segmented. Option A below is therefore the road *not*
> taken; this table prices what it *would* cost to switch to it now.

| artifact | effect | measured |
|---|---|---|
| **Corpus provision identity** | Re-segmenting `273/9` demotes/deletes the section provision (UUID `f("axiom:…/273/9")`) and mints new subsection UUIDs. **Both current dependents ground on `us/regulation/7/273/9`**, so both dangle unless migrated via a `split` event. | 2 modules currently depend on the section provision (`…/273/9.yaml`, `…/273/9/d/6/iii.yaml`); both re-point required. |
| **Reverse index** | Must be regenerated; new subsection provisions appear as new keys; `rulespec-us#523` CI (`git diff --exit-code`) goes red until regenerated. | 1 index file, deterministic regen (already automated in #523). |
| **rulespec-us modules** | The subsection module would have to be **re-grounded** from the section corpus path onto a new subsection corpus provision (and re-pass compile/proof/oracle gates). This is rework of an *existing* module, not net-new. | 1 existing module re-grounded + re-verified; SNAP oracle is CO-only per the plan's 14/56, so no subsection oracle certifies the re-segmented text. |
| **Every other section currently rolled up** | Sets a **precedent**: if `273.9(d)(6)(iii)` forces the *corpus* to subsection depth, the ~thousands of `block-1` section-leaves (17,878 `block-N` at r0) become candidates for the same treatment. That is the corpus-wide re-segmentation the v2 plan explicitly declined to commit to before the oracle spans the surface. | 17,878 `block-N` leaves are the latent scope. |
| **Claims (A4)** | Any claim whose subject embeds the section path must be re-keyed to the subsection. | 2 claims files at present (cheap now, per the plan). |

Option A's true cost is **not** the one module — it is that it commits the corpus
to subsection segmentation as a general policy (re-grounding what already works),
and the corpus has no oracle to certify the re-segmented content across the
surface.

### 3.2 What Option B invalidates

Option B is **already the as-built state for the federal case** (see §1). The
costs below are therefore mostly *zero / already paid*; the only open work is the
us-ma tail.

| artifact | effect | measured |
|---|---|---|
| **Corpus** | Nothing. `273/9` stays one provision; identity preserved; no `split` event; no reverse-index churn. | 0 corpus changes. |
| **rulespec-us modules (federal)** | Already done: `regulations/7-cfr/273/9/d/6/iii` exists (#440) and grounds on the section corpus path. | 0 further work for the federal case. |
| **Program specs (federal)** | The 7 SNAP specs already resolve — the module path equals the scope entry and `known-dangling.yaml` no longer lists the federal entry. | 0 further work. |
| **us-ma tail** | Resolve the 3 remaining us-ma entries as naming-drift / promotion under the identity contract: `365/180/A` → the existing `365/180/block-1` (a `rename`), promote/author `364/945` and the DTA SUA `policies/` module. | 3 entries; mechanical under the path-mapping events. |
| **Subpath-anchor convention** | Make the pattern the federal case already uses explicit and reusable: a subsection reference is carried as **rule-level `source` metadata** in a module whose `corpus_citation_path` stays at the section (as #440 does), and — where a program spec needs to name the subsection directly — as an optional `anchor` on the scope entry (metadata-only for compose). | 0 for the federal case (already this shape); 1 small optional `axiom-programs`/`axiom-compose` schema addition if specs ever need to name a subsection the module path doesn't already encode. |
| **Citation fidelity** | The subsection (`(d)(6)(iii)`) is expressed as `source` metadata on the module's rules (and the fine-grained module path), not as a distinct corpus-provision UUID. | Already the production choice; the exact subsection is preserved and human-legible; a future span-grounding pass can attach a character span into the section text if UUID-level subsection identity is ever needed. |

## 4. Recommendation

**Ratify section-rollup as the standing policy — the module may be as
fine-grained as it needs to be (down to a subsection path), but its
`corpus_citation_path` grounds on the section-level corpus provision and the
exact subsection is carried as rule-level `source` metadata (and, where a spec
must name it, an optional `anchor`). Reserve corpus-level subsection
re-segmentation (Option A) for cases with an executable oracle at that
granularity, done as a deliberate `split` with a path-mapping event.**

This is the pattern the federal `273.9(d)(6)(iii)` case **already uses** in
production (rulespec-us #440); the recommendation is to make it the explicit,
documented default and finish the us-ma tail the same way.

### Rationale

1. **It is what already works.** The federal blocker in #14 was resolved by
   exactly this shape: a subsection-path module grounded on the section corpus
   provision, subsection cited in `source` metadata. Ratifying it codifies a
   proven pattern rather than imposing a new one.

2. **It matches the invariants the v2 plan committed to.** The plan declined
   broad corpus re-segmentation *before an oracle spans the surface* (§5
   invariant 5, red-team finding RT-1). Option A as a *policy* is that
   re-segmentation on the installment plan — the first subsection sets the
   precedent for the other 17,878 `block-N` leaves. Section-rollup keeps the
   corpus unit at the section, where the content and the (CO-only) oracle live.

3. **It preserves identity and costs almost nothing.** Section-rollup changes
   **zero** corpus provisions. Option A mints new UUIDs, forces a `split` event,
   regenerates the reverse index, and re-grounds an existing signed module
   through gates that have no subsection oracle. The reverse index
   (`rulespec-us#523`) makes the asymmetry concrete: `us/regulation/7/273/9` has
   2 module dependents today, both grounded on the section — Option A dangles
   both; section-rollup touches neither.

4. **The subsection reference is not lost.** It lives as `source` metadata on the
   module's rules (`7 CFR 273.9(d)(6)(iii)(D)(3)`) and in the fine-grained module
   path. An optional `anchor` on a program scope entry can name it too. The
   *right* layer for UUID-level subsection precision is a future span into the
   section text, not a separately re-segmented corpus provision.

5. **It does not foreclose Option A where warranted.** When a subsection both
   (a) needs an independently testable rule *that the module path cannot already
   express* and (b) has an executable oracle at that granularity, re-segment the
   corpus *as a deliberate `split`* with the path-mapping event and index regen.
   The policy is "section-grounded by default, corpus subsection when
   oracle-justified," consistent with the plan's B4 coverage-first sequencing.

### Concrete next steps if ratified

1. **Document the pattern** in the `axiom-programs` / rulespec-us contributor
   docs: module paths may be subsection-deep; `corpus_citation_path` grounds on
   the section; subsection precision goes in rule `source` metadata. Cite #440 as
   the reference implementation.
2. **Add an optional `anchor`** to the `axiom-programs` scope-entry schema
   (string; the subpath within the referenced provision; metadata-only for
   compose) for the cases where a spec needs to name a subsection the module path
   doesn't already encode. Low priority — the federal case did not need it.
3. **Finish the us-ma tail** under the identity contract: `365/180/A` → the
   existing `365/180/block-1` (`rename`); promote/author `364/945` and the DTA
   SUA `policies/` module; emit the `rename` events for the corpus-side drift
   (`provision-identity.md` §3). Remove those `known-dangling.yaml` entries as
   they resolve (that file's own rules require it) and drop the `axiom-compose`
   CA-SNAP xfail.
4. **Record corpus subsection re-segmentation as an oracle-gated exception** —
   allowed only as a `split` with an event and a subsection oracle.

### If Max prefers Option A instead

The honest counter-case: corpus subsection-as-provision gives strictly better
provenance (a subsection UUID is more precise than a section provision plus
`source` metadata) and is the natural end-state if the corpus is going to be
span-ground everything anyway (the eval's target architecture). If the decision
is that corpus subsection granularity is the intended long-term unit, the
*cheapest correct* way to start is still an explicit `split` with the event
stream and index regen — never an in-place rename — gated on a subsection oracle
so we do not regenerate content we cannot check. `273.9(d)(6)(iii)` would be a
reasonable first candidate (SNAP is federally uniform, one module serves all 7
states; the homeless-shelter deduction is well-bounded and testable) — but note
that adopting Option A here means *re-grounding a module that already works*, so
the bar should be a concrete provenance need, not tidiness.

## 5. Recommendation in one line

**Ratify section-rollup — subsection-deep modules grounded on the section-level
corpus provision, subsection in `source` metadata — as the standing default, and
allow corpus subsection re-segmentation only where an executable oracle justifies
a deliberate `split`; it is the pattern that already resolved the federal #14
case (#440), preserves provision identity, and honors the v2 plan's rule against
broad re-segmentation before oracle coverage exists.**
