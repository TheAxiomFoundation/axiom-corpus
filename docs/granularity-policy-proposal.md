# Subsection-granularity policy — proposal (issue-14)

Status: **PROPOSAL. Recommends, does not decide.** Max ratifies on the PR.
Phase-A item **A6** (`axiom-rebuild-plan-2026-07-02.md`): *"the issue-14
granularity policy decided (subsection paths: encode-at-subsection vs
section-rollup)."* This document analyzes the choice and makes **one**
recommendation with rationale; the decision is recorded when this PR merges.

Tracking issue: [`axiom-programs#14`](https://github.com/TheAxiomFoundation/axiom-programs/issues/14).
Related: [`schema/citation-path.v1.md`](../schema/citation-path.v1.md),
[`docs/provision-identity.md`](./provision-identity.md), `rulespec-us#523`
(reverse index), `rulespec-us/known-dangling.yaml`.

---

## 1. The problem, precisely

Seven state SNAP program specs, plus three extra `us-ma` state-scope entries,
declare scope entries at a **finer granularity than anything that is encoded or
ingested**. The programs therefore cannot compose into runnable artifacts.

The canonical example from issue #14:

```
regulations/7-cfr/273/9/d/6/iii     <- referenced by 7 SNAP specs
```

But:

- **rulespec-us** encodes 7 CFR 273.9 at **section** granularity only:
  `us/regulations/7-cfr/273/9.yaml`. `git log --all -- "regulations/7-cfr/273/9/d*"`
  is empty — the subsection module has never existed on any ref.
- **The corpus** carries 7 CFR 273.9 as a single provision:
  `us/regulation/7/273/9` (one leaf; no `/d/6/iii` descendant). There is exactly
  one corpus path containing `273/9`, and it stops at the section.

So the reference is dangling on **both** the module side (no `.../9/d/6/iii.yaml`)
and the corpus side (no `.../273/9/d/6/iii` provision to ground it against).

### 1.1 The dangling set (full audit, from issue #14 + `known-dangling.yaml`)

| scope entry | scope | dangling in | what exists instead |
|---|---|---|---|
| `regulations/7-cfr/273/9/d/6/iii` | federal | us-al, us-ca, us-ma, us-nc, us-ny, us-sc, us-tn (7 specs) | section module `regulations/7-cfr/273/9`; corpus `us/regulation/7/273/9` |
| `regulations/106-cmr/364/945/block-1` | state | us-ma | nothing under `364/945*` |
| `regulations/106-cmr/365/180/A` | state | us-ma | `365/180/block-1.yaml` — **`A` → `block-1` naming drift** |
| `policies/dta/snap/fy-2026-cola/heating-cooling-standard-utility-allowance` | state | us-ma | no `policies/` tree at all |

Tally: **1 federal path × 7 specs + 3 us-ma state paths.** Two of the us-ma
entries (`365/180/A`, the DTA SUA policy) are the *program-side face of the
corpus identity drift* documented in `provision-identity.md` §3 — the same
`365/180/A` vs `365/180/block-1` mismatch appears there as a stored-UUID that no
longer derives from its path.

### 1.2 Two distinct sub-problems hide here

1. **True subsection depth** (`273.9(d)(6)(iii)`): the spec wants a rule about
   the homeless-shelter deduction, which lives inside a subsection the corpus
   never segmented below the section.
2. **Naming drift** (`365/180/A` ↔ `365/180/block-1`, `block-1` vs missing
   `364/945`, `policies/` never promoted): the spec references a *label* that
   was re-slugged or never generated. This is not a granularity question — it is
   a rename/promotion question, resolved by the path-mapping events
   (`provision-identity.md` §4) and by promoting the missing modules.

The **policy** decision below is about sub-problem (1). Sub-problem (2) is
tracked but is mechanical clean-up under the identity contract, not a fork in
the road.

## 2. The two options

### Option A — encode-at-subsection

Segment the corpus and rules down to the referenced subsection. Concretely:

1. **Corpus**: re-segment `us/regulation/7/273/9` into its subsection tree so
   `us/regulation/7/273/9/d/6/iii` exists as its own provision (and, to be
   consistent, the sibling subsections too).
2. **rulespec-us**: encode `us/regulations/7-cfr/273/9/d/6/iii.yaml` as its own
   atomic module with a companion test, grounded on the new corpus provision.
3. **Program specs**: leave the scope entries as-is (they already point at the
   subsection); they now resolve.

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

| artifact | effect | measured |
|---|---|---|
| **Corpus provision identity** | Re-segmenting `273/9` deletes the section provision (UUID `f(…/273/9)`) or demotes it, and mints new subsection UUIDs. Any consumer grounded on `us/regulation/7/273/9` dangles unless migrated via a `split` event. | `273/9` currently has **0 module dependents in the reverse index by that exact key** because rulespec's `corpus_citation_path` uses the corpus form and the section is grounded — but the section-backbone module that the income-eligibility work is building **will** ground on it; splitting it out from under that module is the invalidation. |
| **Reverse index** | Must be regenerated; new subsection provisions appear as new keys; `rulespec-us#523` CI (`git diff --exit-code`) goes red until regenerated. | 1 index file, deterministic regen (already automated in #523). |
| **rulespec-us modules** | One new module + companion test to author and get through the encoder's compile/proof/oracle gates. Repeats for every state that needs a *different* subsection (SNAP is federal-uniform here, so likely one module serves all 7). | ~1 new signed module + test; oracle coverage for it does not exist yet (SNAP oracle is CO-only per the plan's 14/56). |
| **Every other section currently rolled up** | Sets a **precedent**: if `273.9(d)(6)(iii)` is encoded at subsection depth, the ~thousands of `block-1` section-leaves (17,878 `block-N` at r0) become candidates for the same treatment. That is the corpus-wide re-segmentation the v2 plan explicitly declined to commit to before the oracle spans the surface. | 17,878 `block-N` leaves are the latent scope. |
| **Claims (A4)** | Any claim whose subject embeds the section path must be re-keyed to the subsection. | 2 claims files at present (cheap now, per the plan). |

Option A's true cost is **not** the one module — it is that it commits the corpus
to subsection segmentation as a general policy, and the corpus has no oracle to
certify the re-segmented content across the surface.

### 3.2 What Option B invalidates

| artifact | effect | measured |
|---|---|---|
| **Corpus** | Nothing. `273/9` stays one provision; identity preserved; no `split` event; no reverse-index churn. | 0 corpus changes. |
| **rulespec-us modules** | Nothing re-authored; the section module already exists and is where the backbone work is landing. | 0 new modules for the federal case. |
| **Program specs** | Edit 7 federal scope entries (+ the us-ma state entries) from subsection to section, and introduce an `anchor` field/convention in the spec schema. Requires `axiom-programs` + `axiom-compose` to understand `anchor` (or to accept section + ignore the anchor as metadata). | 7 spec edits + 1 small `axiom-compose` schema addition. The compose fail-fast validator (issue #14 "related") already lands the machinery to re-point scope entries. |
| **Citation fidelity** | The precise subsection (`(d)(6)(iii)`) is demoted from an addressable provision to an annotation on the section reference. A downstream question "which subsection grounds this rule?" is answered by the anchor, not by a provision UUID. | Acceptable for compose/execution; slightly weaker for span-grounded provenance (the eval's long-term goal). |

## 4. Recommendation

**Adopt Option B (section-rollup with a subpath anchor) as the default policy,
and reserve Option A for cases with an executable oracle at subsection
granularity.**

### Rationale

1. **It matches the invariants the v2 plan already committed to.** The plan
   declined to commit to broad corpus re-segmentation *before an oracle spans
   the surface* (§1, §5 invariant 5, finding RT-1). Option A, applied as a
   policy, is exactly that re-segmentation on the installment plan: the first
   subsection sets the precedent for the other 17,878 `block-N` leaves. Option B
   keeps the encoding unit at the section, where the content and the oracle
   (such as it is) already live.

2. **It preserves identity and costs almost nothing.** Option B changes **zero**
   corpus provisions and **zero** existing modules; it edits 7 spec entries and
   adds one `anchor` convention. Option A mints new UUIDs, forces a `split`
   event, regenerates the reverse index, and requires a new signed module +
   test through gates that have no subsection oracle. The reverse index
   (`rulespec-us#523`) makes this asymmetry concrete: Option B touches nothing it
   indexes; Option A invalidates the section provision the backbone module
   grounds on and every future consumer of it.

3. **The subsection reference is not actually lost.** The `anchor: d/6/iii`
   convention keeps the exact citation as structured metadata on the section
   reference. Compose and the engine only need the section to resolve; the
   anchor preserves the provenance breadcrumb for humans and for a future
   span-grounding pass — which is the *right* layer for subsection precision
   (a character span into the section text), not a separate provision UUID.

4. **It resolves the real blockers now.** All 7 SNAP specs compose the moment
   the entries are re-pointed to the section. The us-ma naming-drift entries
   (`365/180/A` → `365/180/block-1`, missing `364/945`, un-promoted `policies/`)
   are resolved by the same re-pointing plus module promotion under the identity
   contract — not by re-segmentation.

5. **It does not foreclose Option A where it's warranted.** When a subsection
   both (a) needs an independently testable rule and (b) has an executable
   oracle at that granularity, encode it at subsection depth *as a deliberate
   `split`* with the path-mapping event and a regenerated index. The policy is
   "section by default, subsection when oracle-justified," not "never
   subsection." This is consistent with the plan's B4 coverage-first sequencing.

### Concrete next steps if ratified

1. Add an `anchor` field to the `axiom-programs` scope-entry schema (string,
   the subpath within the referenced provision; optional; metadata-only for
   compose).
2. Re-point the 7 federal SNAP scope entries to `regulations/7-cfr/273/9` with
   `anchor: d/6/iii`. Confirm the section backbone carries the homeless-shelter
   deduction (the in-flight income-eligibility work); if not, that content is
   added to the **section** module, not a new subsection module.
3. Resolve the 3 us-ma entries as naming-drift/promotion:
   `365/180/A` → `365/180/block-1`; promote/author `364/945` and the DTA SUA
   `policies/` module; emit `rename` events for the corpus-side drift
   (`provision-identity.md` §3).
4. Remove the corresponding `known-dangling.yaml` entries as they start
   resolving (that file's own instructions require this), and drop the
   `axiom-compose` CA-SNAP xfail.
5. Record subsection-encoding as an **oracle-gated exception** in the
   `axiom-programs` contributor docs.

### If Max prefers Option A instead

The honest counter-case: Option A gives strictly better provenance
(subsection-as-provision is more precise than section+anchor) and is the natural
end-state if the corpus is going to be span-ground everything anyway (the eval's
target architecture). If the decision is that subsection granularity is the
intended long-term unit, then the *cheapest correct* way to start is still to do
it as an explicit `split` with the event stream and index regen — never as an
in-place rename — and to gate it on having a subsection oracle so we do not
regenerate content we cannot check. In that case, `273.9(d)(6)(iii)` is a fine
first candidate because SNAP is federally uniform (one module serves all 7
states) and the homeless-shelter deduction is a well-bounded, testable rule.

## 5. Recommendation in one line

**Section-rollup with a subpath anchor as the default; subsection encoding only
where an executable oracle justifies a deliberate `split` — because it unblocks
all seven specs today at near-zero cost, preserves provision identity, and
honors the v2 plan's rule against broad re-segmentation before oracle coverage
exists.**
