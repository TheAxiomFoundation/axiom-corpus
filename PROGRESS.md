# Israel statute pilot progress

## State

- Worktree: `_worktrees/axiom-corpus-il-ingest`; branch `ingest/il-taxben-pilot`,
  cut from `origin/main` at `f22e9a45`.
- Scope/version: `il/statute` / `2026-09-06-il-taxben-pilot`.
- Bounded pilot on a **secondary consolidation**. The claim is source fidelity,
  not coverage: every provision the captured OpenLaw pages render becomes a row,
  reconciled 1,414 against 1,414 with 0 missing and 0 extra. That is a
  row-generation reconciliation, not a statement that the scope is the complete
  statute as administered, and not certification of anything.
- The ingest manifest is committed **unsigned**; the dispatcher signs it from a
  clean root checkout. CI `guard-ingested` is expected to be red until then. It
  has now been signed twice and invalidated twice by a later repair — most
  recently by review round 2, which changed the provisions and inventory files
  the `3edfd123` signature covered.
- **Merging this PR publishes the release.** `publish.yml` fires on a push to
  `main` touching `manifests/releases/*.json` and uploads, signs and registers
  `il-rulespec-2026-09-06`. Only *activation* is separate. An earlier revision of
  the PR description said publication was outside this PR; it was wrong.

## Done

- Read `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, the Israel campaign brief,
  the binding citation scheme, and the Armenia ARLIS adapter as the template.
- Characterized both hash-pinned snapshots without ever printing raw HTML: the
  ספר החוקים הפתוח (OpenLaw) pages are anchor-structured (`div#law-content`,
  `div.law-number[id="סעיף_…"]`, `div.law-desc`, `div.law-main`,
  `h1.law-part` / `h2.law-section` / `h3.law-subsection`, `span.law-note`), so
  the adapter is anchor-driven, not line-regex driven.
- Verified `expression_date` first-hand against the Knesset registry rather than
  asserting it from the page: OData `KNS_IsraelLaw` returned
  `LatestPublicationDate` 2026-06-08 for IsraelLawID 2000944 and 2026-06-15 for
  2000198, both `LawValidityDesc` תקף. Response captured at
  `ops/il-lane/sources/knesset-israel-law-metadata.json` outside this repo.
- Added `src/axiom_corpus/corpus/israel_openlaw.py` and the
  `extract-il-openlaw` CLI command, grouped under "Extract: international".
- Added `manifests/il-taxben-pilot-openlaw.yaml` pinning both instruments by
  SHA-256, expression date + declared basis, and expected structural counts.
- Found that the Ordinance's full-page Wikisource render is silently truncated
  by MediaWiki's post-expand include limit (`Post-expand include size:
  2097152/2097152 bytes`, 240 omitted-template markers): §§235-247 and all four
  תוספות never render, and §235 was landing as 30,059 characters of MediaWiki
  error text. The adapter now refuses an undeclared truncated render, cuts the
  primary at the start of the damaged section, and completes the document from a
  hash-pinned supplement rendered from the same revision (3079834) via
  `api.php?action=parse`. +49 rows, 0 removed, and no other provision body
  changes.
- Extracted the scope: 2 documents, 1,138 sections, 46 schedule items,
  228 navigation nodes, 1,414 provisions, reconciled 1,414 against 1,414
  inventory entries with 0 missing and 0 extra.
- Repaired the two defects an offline adversarial review verdicted DO-NOT-SHIP:
  editorial-note removal was deleting the statutory tables it should only have
  annotated (NII לוח ח׳2, the §337(א)/§340(א) contribution-rate tables under
  לוח י׳, and לוח י״ז all fell back to heading-only bodies), and h4 statutory
  subheadings were dropped from bodies and overwritten in metadata, so the two
  identically-headed retirement ladders of לוח א׳1 lost גיל הפרישה לגבר /
  גיל הפרישה לאישה. Tables are now identified individually — only a table
  introduced by an unparenthesised, colon-terminated lead-in and carrying no
  note of its own is the project's apparatus — and every h4 stays in the body at
  its printed position and in `metadata.captions` in order.
- Repaired the third defect, which a multi-agent audit of that repair found and a
  second audit widened: `span.law-note` was stripped from every body, so statements
  of legal effect were deleted along with OpenLaw's apparatus. 147 rows lost a note
  whose deletion changes what the row says — 118 a repeal, deletion or expiry marker
  on a limb of a section still in force, 39 a version or applicability qualifier —
  and 30 section bodies were left holding a bare enumerator where a deleted limb had
  been (ITO §5 read `(1) (2) (3) (4) (א) (ב) שר האוצר…`). Three parenthesised shapes
  now stay in the body where the source prints them and are recorded in
  `metadata.statutory_notes`: a repeal/deletion/expiry marker, a colon-terminated
  version or applicability qualifier, and a note inside a table cell. Amendment
  history, OpenLaw's indexed-amount glosses, its footnote letters and its comparison
  lead-in are unchanged and still never reach a body, and a block whose only content
  is a status line still becomes that section's body with `operative: false` — still
  exactly 122 rows.
- Net effect of all three repairs: 1,414 rows before and after, 0 added, 0 removed,
  185 bodies changed (145 section, 22 schedule, 17 sign, 1 chapter), every change
  additive — no row lost a character. 4 of the 18 pilot sections move (ITO §40, §66,
  §120ב, NII §68), so the cost was measured rather than assumed: all 85 verbatim
  proof excerpts in the frozen rulespec-il tree still match exactly as before,
  80 of 85 at every head, 0 that matched stopped matching.
- Repaired the fourth defect, which a peer review of `6b721a7b` found: a note stating
  legal effect for a time window was still deleted when it was printed inline in running
  text rather than in a table cell or with a terminating colon, and a block whose only
  content was a note was assumed to be a repeal/expiry line. NII פרק ז׳ סימן ט׳ lost the
  window its wartime unemployment provisions apply in; NII §340א kept 6.25%/1%/2% and lost
  the 2025–2026 substitutions 7.85%/1.8%/3.6%, §340 lost 0.53%/0.13%, ITO §14 lost the
  instruction to read "five consecutive years" for a 2007–2009 cohort and ITO §35 the
  42-month period for a pre-2022 immigrant. Surveyed all 2,084 `span.law-note`: 10 notes
  across 5 rows moved from `editorial_notes` into the body, none left a body, 1,414 rows
  before and after, and OpenLaw's indexed-amount and average-wage glosses — the same
  `(qualifier: value)` shape over a shekel figure — still never reach one.
- Added `tests/test_israel_openlaw.py` (91 tests) covering the transliteration,
  the false-split hazards, editorial-apparatus removal, the four real table
  shapes and their labels, all four statutory note shapes with negative controls
  for the glosses that must stay out, status lines, schedule binding, manifest
  validation, fail-before-write drift checks, and the checked-in pack.
- Committed the unsigned ingest manifest and the `il-rulespec-2026-09-06`
  release-cut plan; `validate-release` reports 0 issues.

## Next

1. Dispatcher **re-signs** `.axiom/ingest-manifests/il/statute/2026-09-06-il-taxben-pilot.json`
   from a clean root checkout, then CI `guard-ingested` goes green. The first
   signature (commit `da222e7c`) covered the pre-repair artifacts and no longer
   describes the tree; the manifest is committed unsigned again on purpose.
2. Land the PR with a true **merge commit**; never squash or rebase — the
   manifest attests the head of this branch.
3. `il-rulespec-2026-09-06` publishes itself on merge — `publish.yml` uploads,
   signs and registers it. Decide before merging whether that should happen now
   or whether the release selector should be cut in a separate PR; the ingest is
   complete without it. Activation stays separate and is not requested here.
4. Before any Israeli amount is cited as current law, add a separate scope for
   the Tax Authority and National Insurance Institute amount publications and
   for the gazette PDFs of the 2025/2026 amending acts. This scope carries
   statute text only.

## Known limits of this scope

- **Source tier, per act.** Provision text is the he.wikisource.org
  ספר החוקים הפתוח consolidation — a volunteer consolidation, not an official
  gazette text. The Knesset database's "לחוק המלא" link was followed to the
  Wikisource page for the Ordinance (`consolidation-knesset-linked`); the same
  check is still pending for the National Insurance Law, which therefore claims
  only `consolidation-wikisource`. The tier is on every row.
- **The Ordinance is assembled from two rendered fragments.** The full-page
  render cannot carry the whole law (MediaWiki post-expand include limit), so
  §§235-247 and the four תוספות come from a supplement rendered from the same
  revision's wikitext. Both fragments are hash-pinned in the manifest and stored
  in the scope; every row records which one it came from. The National Insurance
  Law's render is undamaged and uses no supplement.
- **Gazette cross-checks done for two provisions only.** §120ב(ה) (the
  2025-2027 indexation freeze, amendment 276, ספר החוקים 3342) and §121's 2026
  bracket edges (amendment 288, ספר החוקים 3511 p.415) both match the captured
  consolidation, checked against the gazette PDFs this session. Every other
  provision in the scope rests on the consolidation alone.
- **§283 of the National Insurance Law appears twice** — the operative text and
  a version conditioned on publication of the 2026 budget law. Both are landed,
  as `section-283` and `section-283-alt2`; this lane does not decide which is
  in force.
- **One transcription defect in the consolidation, carried through unrepaired.**
  ITO §187 reads "בסעיף 59א(א)" and links to a `#סעיף_59א` that does not exist;
  Nevo reads "בסעיף 159א(א)" there and prints that form 22 times with no
  occurrence of the short one. The corpus stores the source verbatim. The spot
  check pins it as the only known dangling internal reference so that any other
  one — which would mean a lost section — fails.
- **One printed-label disagreement.** OpenLaw prints "57א" against the anchor
  `סעיף_57ג`. The anchor wins; `metadata.printed_label_mismatch` records it.
- **Citation-scheme extensions, ratified.** This scope needed two extensions
  beyond the suffix mapping `ops/il-lane/CITATION-SCHEME.md` originally
  enumerated: suffix ordinals past 26 continuing in bijective base-26
  (כז→aa … לד→ah), and `…/schedule-<ident>/item-<ident>` for schedules. The
  dispatcher ratified both on 2026-09-06 and the scheme file now states the
  gematria-value rule through לד=34; a naive letter-position mapping was not
  merely underspecified but collided (כ with יא on ITO §103, §195 and NII §179).
