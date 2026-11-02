# Wyoming EOM "missing Purpose sentence": measured, and no successor cut

Date: 2026-10-20. Branch `discovery/ingest-wy-eom-purpose-successor`, cut from `main`
at `393127f8b`.

**Outcome: the reported fidelity gap does not exist, so no successor scope was built.**
The opening Purpose sentence and every field label of the Wyoming EOM sections are in
the corpus today. They are carried in each block row's `heading` field, not its `body`.
The held scope `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure` is left
exactly as released: no manifest, artifact, lock or selector was touched.

started_at 2026-10-20T19:36:09Z, finished_at 2026-10-20T19:46:30Z, wall time 10m 21s.
Extraction seconds: 0 — no `extract-official-documents` run was made, because no
successor was warranted. The fidelity audit that decided it took 19 s for 121 live
fetches and 121 re-extractions.

## Duplicate-work check

- `gh search prs "wyoming" --repo TheAxiomFoundation/axiom-corpus --state open --limit 20`
  returned nothing.
- `gh search issues "EOM" --repo TheAxiomFoundation/axiom-corpus --state open` returned
  nothing.
- `gh pr list --state open` lists 30 PRs. None names Wyoming, the EOM, the Medicaid
  queue or `manifests/us-wy-medicaid-eligibility-manual.yaml`.
- Merged history holds the scope's own origin (#714, wave-5 Medicaid/CHIP closure) and
  #837's wave-5 union. Neither is open work.
- `origin/discovery/ingest-w8-benefits` (`6bb8a4fcd`, pushed today) points the CHIP
  us-wy and SSI us-wy queue rows at this held scope and records that
  "the held text is a strict subset of what the publisher serves today". This run does
  not contradict that branch: it leaves both rows pointing at the same held scope, and
  it measures that subset relation to be text-equal for 119 of 121 documents. See
  judgment 6 for the two that differ.

## Measured defect scale, all 121 documents

Audit: `scripts/repro/wy_eom_fidelity_audit.py`. Per-document figures:
`docs/ingest-runs/2026-10-20-wy-eom-purpose-successor.json`.

For every one of the manifest's 121 documents the audit fetches the live page, extracts
blocks with that document's own manifest `extraction` options, and compares the result
against the released provision rows for that citation path.

| Measure | Count |
| --- | ---: |
| Documents in the manifest | 121 |
| Reachable, judged by response body | 121 |
| Documents that lose a Purpose sentence | **0** |
| Documents that lose a field label | **0** |
| Documents whose live text is wholly present in the corpus | 120 of 121 |
| Documents whose retained bytes and the live page extract to the same text | 119 of 121 |
| Documents byte-identical to the live page | 0 (see judgment 2) |
| Live Purpose sentences published across the scope | 79 |
| Live Purpose sentences present in the corpus | 79 of 79 |
| Live field labels published across the scope | 262 |
| Live field labels missing from the corpus | **0** |

Released scope shape, read from the provisions JSONL: 458 rows — 121 `document` rows and
337 `block` rows. All 337 block bodies are non-empty. No citation path is duplicated.
The 121 bodyless `document` rows are the shared document extractor's normal shape and
are not a `hollow_document_root` finding, which `content_quality` states explicitly:
a bodyless root with text below it is not a finding.

The two named sections, checked by name:

| Citation path | Purpose sentence | In corpus |
| --- | --- | --- |
| `us-wy/manual/wdh/medicaid/m1800-other-programs-m1804-state-supplemental-payments` | "Purpose: This section will assist in showing the SDX process of how the State Supplemental Payment is issued." | yes, `.../block-1` heading |
| `us-wy/manual/wdh/medicaid/m1800-other-programs-m1803-kid-care-chip` | "Purpose: This section will assist in determining Kid Care CHIP eligibility for children ages 0-18 years." | yes, `.../block-1` heading |

The citation path is `m1800-other-programs-m1804-...`, the report's second spelling. The
first spelling, `m1804-other-programs-m1804-...`, is in neither the manifest nor the
provisions.

## Cause of the finding, in the extraction configuration

All 121 documents carry the same extraction options, and they are correct:

```yaml
extraction:
  html_content_selector: div.UtePc
  html_drop_selectors: [nav, header, "[role='banner']", script, style]
```

`div.UtePc` is the whole served policy container. Its text starts "Eligibility Online
Manual M1804 State Supplemental Payments Purpose: This section will assist in showing
the SDX process", so the Purpose sentence is inside the selected root. Nothing in the
configuration drops it, and no drop selector is implicated: re-extracting with
`html_keep_default_drop_selectors: [header]` and with `html_keep_navigation_blocks: true`
gives the same four blocks and the same text.

What the report saw is the publisher's markup meeting the shared heading walk.
ecom.wyo.gov is a Google Sites page that wraps each field label in an `h3`
(`h3.CDt4Ke.zfr3Q.OmQG5e`), and it puts the entire Purpose sentence inside the first of
them. `_extract_html_blocks` reads an `h3` as a block heading: the `h3` text becomes the
block's `heading` and the text after it becomes the block's `body`. So for M1804:

| Row | heading | body starts |
| --- | --- | --- |
| `block-1` | Purpose: This section will assist in showing the SDX process… | Current Policy Effective Date: July 1, 2021 |
| `block-2` | Reference: | Defining Requirement: 20 CFR 416.2001 |
| `block-3` | Clarifying Information: | 1. The payment can be made part of the estate… |
| `block-4` | Worker Responsibilities: | Verifying Payment Information… |

A reader who inspects only `body` sees the text begin at "Current Policy Effective
Date:" and the labels gone. Both are present one field over. `heading` is a first-class
provision field, written by `writer.py`, read by `content_quality.py` and the encoder,
and served with the row; it is not a derived or discarded field. No function under
`src/` was read as defective and none was modified.

## Successor scope and lineage

None was cut. Had one been warranted, its version string would have been
`2026-10-20-wy-medicaid-eligibility-manual-purpose-labels`, by the
`2026-10-20-wy-medicaid-eligibility-manual-<reason>` form, with `<reason>` naming the
two text classes the repair would restore. It is recorded here only so a later run that
does find a repairable defect does not have to re-derive the name.

The repo's successor convention, read from `docs/ingest-runs/2026-10-13-hollow-root-successors.md`
(108 successors for the hollow-document-root fixes), is the precedent that would govern
such a build, and it is worth stating because it is what makes "no successor" the
cheaper outcome:

- A merged scope is immutable, so a fix reaches the corpus only through a successor.
- A successor repeats its predecessor's citation paths by design. That is not a
  collision. The paths coexist because the two scopes are distinct scope versions: a
  selector names one scope version, so a release either names the predecessor or names
  the successor, never both. The precedent's successors keep the original's capture date
  and sort after it, so the release gate's `scope_monotonicity` check reads the swap as
  an advance.
- The release lineage supersedes by selector membership, not by deletion: the controller
  swaps the scope version named in the selector. Nothing is removed from the corpus.

Because no successor exists, there is nothing to swap and no selector changes.

## Reviewer judgments

1. **The reported defect is not a defect; it is a field-location misreading.** 0 of 121
   documents lose a Purpose sentence and 0 lose a field label. 79 Purpose sentences and
   262 field labels are all present. Cutting a successor to restore text that is already
   held would add a scope version, a signing and a selector swap and change no text. I
   judge that not worth cutting, which is the decision step 1 of the work order reserved
   for this measurement.
2. **Byte-identity is the wrong test for this publisher, and its 0 of 121 is not a
   finding.** Google Sites re-renders the page per request, so no retained file equals a
   fresh fetch byte for byte. The test that carries meaning is text equality after
   extraction, and that is 119 of 121. I report the byte figure only so it is not later
   mistaken for evidence of drift.
3. **Scope membership of the Purpose text should not be "fixed" by moving it into
   `body`.** The heading/body split follows the publisher's own `h3` markup. Flattening
   it would need a change to a function under `src/`, which this run is forbidden to make
   and which I would argue against anyway: the split is faithful to the source and other
   scopes depend on the same walk.
4. **Coverage against the live navigation is 121 of 129 links, and the gap is 1 real
   page, not 21.** The publisher's index lists 129 links; the manifest covers 121 and
   omits 8. Of those 8, five are site front matter or indexes (`/home`, `/welcome`,
   `/whats-new`, `/fact-sheets` at 37 characters, `/tables` which is the list of tables),
   and `/tables/table7` and `/tables/table9` serve 25 characters each — the site title
   alone, their data being in images. Only `/tables/table4` (Cost of Living Adjustment)
   serves real text the corpus lacks: 147 characters of caption and effective date, with
   the figures in three images. The report's "about 128 sections against 107 recorded"
   does not reproduce; the recorded figure is 121.
5. **I judge `/tables/table4` too thin to carry a successor on its own.** Table pages in
   this manual publish their data as images throughout — `tables/table6`, which the
   manifest does hold, serves 57 characters. Adding table4 is a manifest addition for a
   future dated capture, not a repair of released bytes. I leave it to the controller
   rather than acting on it, because it changes scope membership.
6. **Two documents have drifted at the publisher since the 2026-09-15 capture, in
   opposite directions, and neither is an extraction fault.**
   `us-wy/manual/wdh/medicaid/m800-resources-m801-counting-resources` block-3 has gained
   47 words at the publisher (384 words held, 431 served); this is the single document
   whose live text is not wholly in the corpus. `us-wy/manual/wdh/medicaid/tables-table6`
   has lost text at the publisher: the corpus holds a 37-word heading
   ("Effective Date: March 1, 2022") and the citizenship/immigrant eligibility table
   text, while the live page now serves 6 words, the rest having moved into images. So
   the corpus is in one place behind the publisher and in another place richer than it.
   A dated snapshot scope is expected to diverge from a live site after its capture date;
   this is a currency question for a future refresh, not a fidelity repair, and it does
   not contradict `ingest-w8-benefits`, whose two queue rows cite sections that are
   neither of these two.
7. **If the whole manual were ever rebuilt, it should be rebuilt whole, not per
   document.** Scope membership is per scope version, so a successor covering only the
   affected documents would hold a partial manual and the selector would then have to
   name two scope versions to serve the manual — which the precedent's one-scope-per-
   selector lineage does not do. The consequence either way: a whole-manual successor is
   a single selector swap and the predecessor leaves release membership intact; an
   affected-documents-only successor would force the controller to keep the predecessor
   in the release alongside it, which is the layered-serving case (#728/PR 779) and not
   settled convention. That argument is recorded for the refresh decision; it does not
   apply today, because nothing was built.
8. **GitNexus MCP tools were unavailable in this session.** No library function under
   `src/` was modified. The audit script only calls `_extract_html_blocks` to read.

## Artifacts

- `docs/ingest-runs/2026-10-20-wy-eom-purpose-successor.md` — this note.
- `docs/ingest-runs/2026-10-20-wy-eom-purpose-successor.json` — per-document audit
  figures for all 121 documents.
- `scripts/repro/wy_eom_fidelity_audit.py` — the audit, re-runnable.
- No scope, manifest, lock or selector was added or changed. `data/corpus` is unchanged;
  nothing was signed or published.

## Rebuild commands

The audit, from a checkout with the dev extra synced:

```bash
uv run python scripts/repro/wy_eom_fidelity_audit.py \
  --manifest manifests/us-wy-medicaid-eligibility-manual.yaml \
  --base <corpus base> \
  --scope us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure \
  --out docs/ingest-runs/2026-10-20-wy-eom-purpose-successor.json \
  --workers 4
```

It fetches 121 live pages over TLS with verification on. No mirror, repost, proxy or
archived copy is read, and reachability is judged by the response body.

## Tests

`uv sync --extra dev` exited 0. Both runs are
`AXIOM_CORPUS_PARTIAL_TESTS=1 uv run pytest -q -m "not integration and not slow"
-k "manifest or official_documents or discovery"`.

| Run | Exit | Result |
| --- | ---: | --- |
| Baseline, before the first edit | 1 | 18 failed, 341 passed, 2 skipped |
| Final | 1 | 18 failed, 341 passed, 2 skipped |

The sorted FAILED lists are identical. The 18 are pre-existing and none is Wyoming: they
are the Armenia ARLIS, Belgium rulespec (x2), NY TANF compatibility (x2), Wisconsin PIT
West, Israel OpenLaw, SC Act 110, AK/CT/MI/MT/ND/NY SNAP manual and SNAP child-support
source tests, which read retained artifacts this checkout's `data/corpus` does not hold.

## What the controller must do for release membership

1. **Nothing, for the reported defect.** `us-wy/manual/2026-09-15-medicaid-eligibility-manual-closure`
   stays in every release that names it. There is no successor and no selector swap. Any
   backlog item that asks for a Wyoming EOM Purpose-sentence successor should be closed
   against this note.
2. **Leave `origin/discovery/ingest-w8-benefits` as it stands.** Its CHIP us-wy and SSI
   us-wy rows correctly point at this held scope, and the text they rely on is held.
3. **Decide two currency questions, both out of this run's scope.** Whether to schedule a
   dated refresh capture of the manual, which would pick up the 47 added words in
   `m801-counting-resources` and would also re-capture `tables-table6` in its thinner
   live form — the second is a loss, so a refresh is not strictly an improvement; and
   whether a refresh should add `/tables/table4`. Both change scope membership and so are
   the controller's to decide, not a reviewer's.
