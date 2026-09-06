# il: Israel statute ingest (Income Tax Ordinance + National Insurance Law) — pilot

Bounded Israel pilot scope for supervised RuleSpec-IL encoding. **Merge commit only** —
this PR carries an ingest manifest; squashing or rebasing breaks the attested ancestry.

## Documents

| instrument | Knesset IsraelLawID | sections | schedule items | navigation nodes | rows |
|---|---|---|---|---|---|
| פקודת מס הכנסה [נוסח חדש] — Income Tax Ordinance [New Version] | 2000944 | 577 | 16 | 92 (16 parts, 41 chapters, 31 signs, 4 schedules) | 686 |
| חוק הביטוח הלאומי [נוסח משולב], התשנ״ה–1995 — National Insurance Law [Consolidated Version] | 2000198 | 561 | 30 | 136 (0 parts, 22 chapters, 88 signs, 26 schedules) | 728 |
| **total** | | **1,138** | **46** | **228** | **1,414** |

Scope `il/statute`, version `2026-09-06-il-taxben-pilot`. Coverage reconciles
**1,414 provisions against 1,414 source-inventory entries, 0 missing and 0 extra**. That is
a row-generation reconciliation — every entry this adapter derived from the snapshots became
a row and no row came from anywhere else. It is not a statement that the scope is the
complete statute as administered: it is the OpenLaw consolidation as captured on
2026-09-06, and the transcription defect found inside that consolidation is recorded below
rather than repaired.

## Sources, and the tier caveat

Both instruments come from the ספר החוקים הפתוח (OpenLaw) consolidation on
he.wikisource.org — the page the Knesset National Legislation Database itself links to
as "לחוק המלא", because the Knesset's own consolidated full text is behind a
client-rendered SharePoint app that returns a JavaScript shell to a plain fetch.

| file | url | sha256 | retrieved |
|---|---|---|---|
| `ito-wikisource.html` | https://he.wikisource.org/wiki/פקודת_מס_הכנסה | `87535c2b8cd8aa50b27d32301dc2ddd768390ef64e9fb4f391c3e65fe99dc228` | 2026-09-06T11:41:55Z |
| `ito-wikisource-tail-235-247.html` | he.wikisource.org `api.php?action=parse` over revision 3079834's own wikitext tail | `6cc14dd6bdd6caf14d1f0d63a6f9f74bc83706aefae46b000933d82d84abb9e8` | 2026-09-06T12:31:34Z |
| `nii-law-wikisource.html` | https://he.wikisource.org/wiki/חוק_הביטוח_הלאומי | `7dbaaa757912c71b361381640d2578bf2c6ab52f2002817b85d677c2267f0715` | 2026-09-06T11:41:55Z |

**This is a secondary consolidation, not an official gazette text.** `AGENTS.md` prefers
primary official government sources; this scope is the explicitly directed non-canonical
experiment for the Israel pilot, and it says so on every row (`metadata.source_tier`).
The two acts declare **different** tiers, because the evidence differs: the Knesset
database's "לחוק המלא" link was followed to the Wikisource page for the Ordinance
(`consolidation-knesset-linked`), and that check is still pending for the National
Insurance Law (`consolidation-wikisource`). Israeli Copyright Act 5768-2007 §6
places no copyright in statutes; the OpenLaw project's *editorial* layer is CC BY-SA and is
deliberately excluded from provision bodies (see below), so only the statutory text is stored.

Raising the National Insurance Law to the Ordinance's tier was attempted and did not
succeed here: `KNS_DocumentIsraelLaw` is empty for both IsraelLawIDs, so OData exposes no
full-text link, and the Knesset law page itself is behind bot protection (HTTP 247, a
497-byte challenge shell, for every plain fetch). The "לחוק המלא" check needs a real
browser, which this lane does not have; until someone runs it, the act keeps the lower
tier rather than inheriting the Ordinance's.

`expression_date` is **not** taken from the page. It comes from the Knesset registry — OData
`KNS_IsraelLaw.LatestPublicationDate`, queried 2026-09-06: 2026-06-08 for IsraelLawID 2000944
and 2026-06-15 for 2000198, both `LawValidityDesc` תקף. The basis string is recorded on every
row as `metadata.expression_date_basis`.

## The Ordinance's full-page render is truncated, and the adapter refuses to ingest it blind

The Ordinance is large enough that its Wikisource full-page render hits MediaWiki's
post-expand include budget **exactly** — the page's own parser report reads
`Post-expand include size: 2097152/2097152 bytes` — after which MediaWiki silently stops
expanding templates and emits `<!-- WARNING: template omitted, post-expand include size
too large -->` in their place. There are **240** such markers in the snapshot. The damage
is not cosmetic: §§235–247 and all four תוספות never render at all, and §235 is left
half-expanded.

The adapter now treats that as a first-class, declared condition:

- If a render carries the marker and the manifest does **not** declare
  `render_truncated_after_section`, extraction fails. If the manifest declares truncation
  and the render is undamaged, extraction also fails. Both directions are tested.
- The primary is cut at the **start of the section the truncation lands inside** (§235),
  not at the marker — a half-rendered provision is worse than an absent one — and the
  adapter asserts that the last whole section it parsed is the declared one.
- The tail is supplied by a hash-pinned supplement rendered from **the same revision**
  (3079834, the revision id in the primary snapshot's own page variables) by posting that
  revision's wikitext tail to `api.php?action=parse`, so it stays under the budget.
  Reproduction recipe and provenance:
  `ops/il-lane/sources/ito-wikisource-tail-235-247.html.provenance.json`.
- Fragments share one navigation context, so a section that arrives in the supplement
  still hangs off the חלק and פרק it belongs to, and every row records the sha256 of the
  fragment it was actually read from.

Effect on the scope: **+49 rows, 0 removed**. 29 new sections (235א…247), 4 תוספת
headings with their 16 items, and §235 goes from **30,059 characters of MediaWiki
error text** to the 1,750-character section it actually is. No other provision body in
the scope changes — verified row by row against the previous artifact.

Two smaller fixes ride along: תוספת schedules are recognized (the Ordinance says תוספת
where the National Insurance Law says לוח) with ordinal-word headings resolved to their
anchor identifiers (תוספת ראשונה א׳ → `schedule-1a`), and the project's own bilingual
glossary and "not legal advice" disclaimer — both editorial, both in the tail — are
excluded by name rather than by accident.

## Three adapter defects two adversarial audits found, and their repair

An offline adversarial audit of this branch verdicted it DO-NOT-SHIP for two defects that
deleted statutory content. A second, multi-agent audit — of the repair itself — found a
third, wider one: the adapter deleted every `span.law-note` from every body, and some of
those notes are the statute saying a limb is repealed, or which of two competing versions
a text is. All three are fixed here.

The review's reproduction script, `ops/il-lane/review-work/corpus-reproduce.py`, is pinned
to the pre-repair commit `da222e7c` and loads a frozen copy of the pre-repair adapter, so it
cannot be pointed at this head; it still reports the original three drops, which is how it
stays a baseline. The head is checked by the repo's own tests instead — see "Checks" — and
by a copy of that script re-pinned to this branch, kept in the lane directory.

1. **Editorial-note handling deleted the statutory tables it should only have annotated.**
   `_render_law_main` removed *every* table from a note-carrying block and, when nothing
   remained, discarded the whole block. Three incorporated statutory tables were lost, each
   row falling back to its own heading so nothing read as empty: NII **לוח ח׳2** (the
   §223 service-value table), the **§337(א)/§340(א) contribution-rate tables** under
   **לוח י׳** — the rates NII §337(א)(1) incorporates by reference — and **לוח י״ז** (the
   §384א benefit / legal-source / information table). Tables are now identified one at a
   time by the structure above. The ITO §121 comparison apparatus is still dropped; its
   one-line lead-in is recorded in `metadata.editorial_notes`, and the seven tables it
   introduces are not recorded anywhere — they are OpenLaw's own restatement of §121 for
   2019-2027, and §121's operative text is in its own row.

   | row | before | after |
   |---|---:|---:|
   | `national-insurance-law-1995/schedule-h2` | 7 chars (heading only) | 2,092 chars |
   | `national-insurance-law-1995/schedule-j/sign-1` | 40 chars (heading only) | 3,085 chars |
   | `national-insurance-law-1995/schedule-q` | 503 chars (definitions only) | 9,815 chars |

2. **Statutory table labels were discarded.** h4 headings were dropped from bodies and
   overwritten in `metadata.caption`, so the two retirement-age ladders of **לוח א׳1** —
   which share the identical header `חודש הלידה | גיל הזכאות (בשנים)` — lost
   **גיל הפרישה לגבר** and **גיל הפרישה לאישה**, the only thing distinguishing which sex
   each applies to. Both labels are now inline, each immediately above its own ladder, and
   every subheading is kept in `metadata.captions` in printed order.

3. **`span.law-note` was stripped from every body, deleting statements of legal effect
   along with the apparatus.** Fixing (1) made this visible: it put both §337(א)/§340(א)
   contribution-rate tables back into `schedule-j/sign-1`, and the row then printed two
   tables with the identical header `טור א׳ | טור ב׳ | …` back to back, the line between
   them a data row, while the two labels that say which is which —
   **(הוראת שעה לשנים 2025–2026):** and **(הנוסח הקבוע):** — sat in a flat, positionless
   `editorial_notes` list. The two tables differ materially (employee deduction
   5.55 / 4.47 / 6.92 against 3.85 / 2.87 / 4.61). The same stripping was doing this
   across the scope:

   - **147 rows** lost a note whose deletion changes what the row says — **118** a repeal,
     deletion or expiry marker on a limb of a section that is still in force, **39** a
     version or applicability qualifier, **10** both.
   - It left **30 section bodies holding a bare enumerator** where a deleted limb had
     been. ITO §5 read `(1) (2) (3) (4) (א) (ב) שר האוצר…` — five deleted limbs collapsed
     into a run of empty labels flowing into the text of the one that survives.
   - NII §348(ה) and §158 printed a permanent version and its temporary-order replacement
     consecutively, the second unnumbered and unlabelled. ITO §11's confrontation-line
     credits read as permanent with their 2026-2029 windows removed. NII לוח ט״ז1's whole
     body lost `(הוראת שעה מיום 1.1.2026 עד יום 31.12.2035):`.

   Three parenthesised shapes reached the body at their printed position after this
   round: a repeal, deletion or expiry marker; a colon-terminated version or applicability
   qualifier; and a note inside a table cell. A fourth was added in review round 2 below,
   because that set still deleted a substitution printed inline in running text. They are recorded in `metadata.statutory_notes`. Everything
   else is unchanged — bracketed amendment history, OpenLaw's indexed-amount glosses
   (`(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)`), its bare footnote letters and its one
   comparison lead-in still never reach a body, and a block whose only content is a status
   line still becomes that section's body with `operative: false` (still exactly 122 rows).

Effect on the scope: **1,414 rows before and after — none added, none removed**; **185
bodies changed** (145 section, 22 schedule, 17 sign, 1 chapter), every change additive —
no row lost a character, a line gains a prefix. **4 of the 18 pilot sections move** (ITO
§40, §66, §120ב and NII §68), which is a change from the earlier position that no section
body moved, so it was measured rather than assumed: all **85** verbatim proof excerpts in
the frozen rulespec-il tree were checked against the row each cites, **80 of 85 matched
before and 80 of 85 match after, and 0 excerpts that matched stopped matching** — the
insertions fall where no excerpt spans. (The five non-matches are the pre-existing ones the
review documented: four historical §121 expressions and one policy body.)

The focused suite grew 71 → 84 in that round: fourteen structural unit tests over a
purpose-built fixture carrying all four table shapes, all three note shapes and three
negative controls, and one test pinned to the committed rows. Review round 2 below takes
it to 91, and the figures in this section are that round's measurement — the current ones
are under "Checks".

## Adapter

`src/axiom_corpus/corpus/israel_openlaw.py`, CLI `extract-il-openlaw`, modelled on the
Armenia ARLIS adapter: manifest-pinned, hash-verified, fully parsed and count-checked before
the first artifact is written.

The OpenLaw pages are anchor-structured, so the parser is anchor-driven rather than
line-regex driven. That is what makes it safe on Israeli section numbering:

- **Sub-item anchors fold, they do not split.** `div.law-number` with `id="סעיף_2"` opens
  §2; the same class with a *dotted* id (`סעיף_2.1`) is a sub-item whose text belongs to §2.
  An in-text cross-reference such as "יהא משתלם לפי סעיף 121ב" never opens a section,
  because it is not an anchor.
- **Hebrew suffixes transliterate by enumeration ordinal (gematria), not letter position.**
  121ב → `section-121b`, 66א → `section-66a`, 103יא → `section-103k`, 103כ → `section-103t`.
  A letter-position mapping would collide כ with יא on four real sections (ITO §103, §195;
  NII §179) and ל with יב on one. Ordinals past 26 continue in bijective base-26, which the
  National Insurance Law needs: 179לד → `section-179ah`. Interleaved arabic runs pass
  through: 64א7ב → `section-64a7b`, 75טז1 → `section-75p1`.
- **`span.law-note` is OpenLaw's apparatus nearly everywhere — but not everywhere, and the
  tables it annotates are never apparatus.** Amendment-history brackets (`[תיקון: …]`), the
  project's indexed-amount glosses (`(נקוב לשנת 2015; בשנת 2023, 141,840 ש״ח)`), its bare
  footnote letters and cross-reference notes stay out of bodies and are preserved in
  `metadata` (`amendment_history`, `editorial_notes`). Four parenthesised shapes do reach
  the body, because deleting them changes what the row says rather than how it reads: a
  **repeal, deletion or expiry marker** on a limb of a section that is still in force
  (`(בוטל).`, `(נמחקה);`, `(פקע).`); a **colon-terminated qualifier** saying which of two
  competing versions a text is or when it applies (`(הנוסח הקבוע):`,
  `(הוראת שעה לשנים 2026 עד 2029):`, `(החל מיום 1.1.2030):`); a note **inside a table
  cell**, the statute's own temporary-order substitution for that cell's value
  (`(הוראת שעה בשנים 2024 עד 2027: 2.06)`), which carries no trailing colon and so needs its
  own limb; and the same **substitution printed inline in running text**
  (`(בשנים 2025–2026: 7.85%)` against NII §340א's 6.25%,
  `(עבור מי שעלה לפני שנת 2022: 42 החדשים)` against ITO §35's 54 months), recognised by
  naming a temporary order, instructing a re-reading (`במקום`), or carrying the shape
  `(qualifier: replacement)`. All are listed in `metadata.statutory_notes` — 151 rows.
  A block whose *only* content is a status line is unaffected and still becomes that
  section's body with `operative: false`; a note-only block that is **not** a status line
  is the label it prints, and stays in the body.
  The line between an inline substitution and one of the project's own value glosses is
  the replacement itself: `(נקוב לשנת …)`, `(נכון לשנת …)` and any note replacing a shekel
  figure state a value the statute leaves to indexation, and the citation scheme takes
  current-year regulated amounts only from official publications captured under
  `il/policies/`. Those stay apparatus even when they carry the same internal colon — ITO
  §9א's and §47's average-wage figures do.
  A table is removed only when OpenLaw introduces it as apparatus of its own: an
  unparenthesised, colon-terminated lead-in ("להלן מדרגות המס לשנים 2019 עד 2027:") over a
  table that carries no note itself. That is the 2019–2027 comparison under §121, and
  nothing else in either instrument.
- **h4 subheadings stay with the table they label.** A schedule prints its enabling-section
  caption under its own name, and below that the applicability labels that tell otherwise
  identical tables apart — "גיל הפרישה לגבר" / "גיל הפרישה לאישה" over לוח א׳1. Both kinds
  stay in the body at their printed position and in `metadata.captions` in printed order.
  A navigation node's body leads with its own heading, so a content-bearing לוח does not
  read as a bare table.
- **A note-only block that is the section's own status line** — (בוטל), (פקע), (נמחק) —
  becomes the body, with `metadata.operative = false`. 122 rows.
- **Identity is verified against the page**: the `h1.law-title` must equal the manifest
  title and the page's header line must open with the manifest's IsraelLawID.
- Text is NFC throughout; `language: he` on every row.

Citation paths follow `ops/il-lane/CITATION-SCHEME.md`: sections are flat
(`il/statute/income-tax-ordinance/section-121`) with nested navigation parents
(`…/part-7/chapter-1`), matching the ARLIS precedent. Two documented extensions, flagged
rather than assumed: suffix ordinals past 26 (bijective base-26), and schedules as
`…/schedule-<ident>/item-<ident>`.

## Two independent checks of the captured text against the official gazette

Neither is part of the scope; both are evidence that the consolidation is faithful where
the pilot leans on it hardest.

1. **§120ב(ה), the 2025–2027 indexation freeze.** Amendment 276 (ספר החוקים 3342,
   26.12.2024) inserted it. The captured §120ב body carries it verbatim — "ב־1 בינואר של
   שנות המס 2025 עד 2027 לא יתואמו הסכומים… והסכומים באותן שנות מס יהיו כפי שהיו ביום
   כ׳ בטבת התשפ״ד (1 בינואר 2024)…".
2. **§121's 2026 bracket edges.** Amendment 288, chapter ג' of the 2026 Economic
   Efficiency Law (ספר החוקים 3511 p.415, 31.03.2026), replaces §121(א)(1) with 301,200,
   §121(א)(2) with "מ־301,201… עד 560,280… – 35%", §121(ב)(1)(ג) with "…עד 228,000
   שקלים חדשים –", and §121(ב)(1)(ד) with "מ־228,001… עד 301,200… – 31%", effective
   1 January 2026. Those are exactly the edges in the captured §121 body.

Together they answer a question the pilot brief left open — whether the 20%/31% bands
widened for 2026 or were frozen. Both: §120ב(ה) freezes *indexation* for 2025–2027, and
the 2026 budget law amended the *statutory amounts* directly, with §7 of that chapter
splicing the new amounts into the frozen baseline. The corpus scope stores the
consolidated §121 and §120ב text; it does not itself assert that reconciliation.

## Spot checks (62 checks, all green)

`ops/il-lane/corpus-spotcheck/spotcheck.py`, log alongside.

- §121 (שיעור המס ליחיד) carries 10/14/20/31/35/47 and the captured bracket edges
  84,120 / 120,720 / 228,000 / 301,200 / 560,280 — and **excludes** the editorial
  history table, which is recorded in metadata instead.
- §34 reads "…יובאו בחשבון שתי נקודות זיכוי" — **two** credit points; §36 adds the
  ¼ travel point, rendered inline as `1⁄4`. (The TaxBEN 2.25 is 2 + ¼, not a §34 figure.)
- §121ב present (3% surtax); NII §65, §66, §335 present; NII §66 still cites
  "סעיף 121ב לפקודת מס הכנסה", so the two instruments share one slug convention.
- Every recovered tail section and תוספת is present; no MediaWiki template name and no
  omitted-template warning survives in any body; the glossary and disclaimer are absent.
- Citation paths unique; no row with an empty body; `source_as_of`, `expression_date`
  and `language: he` populated on every row; every parent resolves inside the scope;
  every body NFC-normalized; every citation path an ASCII slug.

Two of the checks are deliberately **not** self-referential — the manifest's
`expected_*` counts were derived from the same parse they guard, so they cannot detect a
render that was incomplete before parsing began. These read the snapshots independently:

- **Every navigation entry in each page's own table of contents is ingested** — 0 absent
  for both instruments. (The corpus additionally carries 4 ITO chapters the table of
  contents omits: three print `(בוטל)` inside their own heading and the fourth is a 2003
  temporary provision. They carry that heading as their body. `operative: false` is a
  section-level marker — it is set from a note-only `law-main` block, so it is on 122
  `section` rows and on no navigation row.)
- **No internal cross-reference points at a section the ingest lacks.** The Ordinance
  links to 578 distinct sections from inside its own text and the National Insurance Law
  to 560; every one resolves, with a single documented exception below.

## Known limits

- Statute text only. No regulations, no Tax Authority / National Insurance Institute
  amount publications, no gazette-verified amendment history. Current-year regulated
  amounts must not be taken from this scope.
- NII §283 is printed twice by OpenLaw — the operative text and a version conditioned on
  publication of the 2026 budget law. Both land, as `section-283` and `section-283-alt2`,
  declared in the manifest so an *undeclared* duplicate anchor stays a hard error. This
  PR does not decide which is in force.
- OpenLaw prints "57א" against the anchor `סעיף_57ג`; the anchor wins and
  `metadata.printed_label_mismatch` records the disagreement.
- **A transcription defect in the consolidation, carried through unrepaired.** ITO §187
  reads "…הפרשי הצמדה וריבית כמשמעותם בסעיף 59א(א)" and links to `#סעיף_59א`, which does
  not exist. Nevo's consolidation of the same provision reads "בסעיף 159א(א)" — the
  section that actually defines הפרשי הצמדה וריבית — and prints that form 22 times with
  no occurrence of the short one. So the OpenLaw text has dropped a digit. The corpus
  stores the source of record verbatim rather than correcting it; the spot check pins
  this as the one known dangling reference, so any *other* one fails. It is a concrete
  instance of what the secondary-consolidation tier caveat is for, and it does not touch
  any provision the pilot encoding cites.
- The National Insurance Law's own render is **not** truncated (0 markers), so it needs no
  supplement; that is asserted by the adapter, not assumed.
- **Tables are rendered as pipe-joined lines, and that rendering is lossy in two ways the
  second audit measured.** A cell holding a line break becomes several body lines, so a
  wide row does not read as one row — 9 of the 21 table-bearing rows are affected. And a
  cell that is empty in the source is dropped rather than emitted as an empty field, so the
  two `סך הכל` rows of `schedule-j/sign-1` carry 10 fields where the data rows carry 11;
  no characters are lost, but column alignment cannot be relied on. Anything that reads a
  rate out of these tables must read it against the source, not by column position.
- **The block-level filter keeps only `law-main`, `law-desc` and `law-number`.** Anything
  else that is a direct child of `div#law-content` is dropped without a counter: in these
  two pages that is the NII promulgation and ministerial power-transfer notices and both
  acts' signature blocks. The scope is the enacted text, not the page.
- `metadata.editorial_apparatus_removed: true` is a source-level constant, not a per-row
  finding — it records that the adapter runs the filter, not that a given row had apparatus
  in it. Two rows now have no editorial notes at all and still carry the flag.
- **A note-only block in OpenLaw's own voice still stays out of the body.** After the
  round-2 fix, a block whose only content is a note reaches the body when the note is
  parenthesised — that is the statute's own labelling idiom (`(הנוסח הקבוע):`,
  `(הוראת שעה מיום … עד יום …):`). Two blocks in the capture state a sign's temporal
  validity in an *unparenthesised sentence* instead — `תוקף סימן זה מיום כ״ב בתשרי
  התשפ״ד (7 באוקטובר 2023) ועד יום כ״א בתשרי התשפ״ו (13 באוקטובר 2025).` and
  `תוקף סימן זה שלוש שנים מיום כ״ב בתשרי התשפ״ד (7 באוקטובר 2023).` — and are kept out,
  in `metadata.editorial_notes`, on the same principle that keeps out the five other
  unparenthesised note-only blocks (`ראו סימולטור לחישוב מס הכנסה באתר רשות המסים.`,
  `לוח זה פורסם במקור בתקנות …`, `ראה תחילה, תחולה והוראות מעבר … בסעיף 29 לחוק …`).
  Those five are unmistakably the project addressing the reader; the two `תוקף` sentences
  are a closer call, and are named here rather than decided quietly.
- **The editorial-table rule marks every later table in the note's container.** Once an
  unparenthesised lead-in is seen, each following table that carries no note of its own is
  treated as part of the apparatus it introduced, with no bound on intervening content.
  That is right for the one block where it fires and is untested against a re-capture that
  interleaves statutory text; the snapshots are hash-pinned, so a re-capture is a new
  review, not a silent change.

## Merging this PR publishes the release — read this before you merge

`manifests/releases/il-rulespec-2026-09-06.json`, one scope, quality profile
`complete-expression-dates-v1`. `validate-release` reports 0 issues, 0 warnings locally.

**Adding that file has an external effect on merge, and an earlier revision of this
description got it wrong.** `.github/workflows/publish.yml` triggers on `push` to
`main`/`master` with `paths: manifests/releases/*.json`; it takes the added or modified
selector out of the merge diff and runs `scripts/publish_corpus.py`, which validates the
cut, writes content-addressed artifacts to R2 and versioned rows to Supabase, reads them
back, **signs the release object with the Ed25519 release key**, and stages it through
`scripts/stage_release_object.py`. So merging this PR uploads, signs and registers
`il-rulespec-2026-09-06` in production.

What merging does **not** do is move serving. Activation is a separate, deliberate step
(`scripts/activate_release.py`, previewable with `--dry-run`) because it repoints the
per-scope serving map and can displace another jurisdiction's release
(axiom-corpus#408). This PR does not request activation, and nothing reads `il` until
someone runs it.

If the reviewer does not want publication to fire on merge, drop
`manifests/releases/il-rulespec-2026-09-06.json` from this PR and cut it separately; the
ingest is complete without it.

## The ingest manifest is unsigned again at this head

The manifest has been signed twice and invalidated twice by later repairs, and the second
of those is this round: the signature committed in `3edfd123` (over the tree at
`152a276f`) covered a provisions file and an inventory file that the round-2 classifier
fix has now changed. It is re-attested **unsigned** at the head of this branch with
`build_ingest_manifest()` over the same six applied files (the supplement HTML is the
sixth) and the same recorded command; no signing key is present or used in this lane.

Until the dispatcher re-signs from a clean root checkout, CI "Guard generated corpus
artifacts" fails with `Missing ingest manifest signature.` by design, and nothing else in
that job fails.

## Review round 2 — three findings, and what changed

A peer review of the previous head (`6b721a7b`) returned `changes_requested` with three
findings. All three are addressed here.

**1 (HIGH) — a standalone applicability label was discarded as a status line.**
`_render_law_main` cleared the keep set for any block whose only content was a note, on
the assumption that such a block is always a repeal/expiry line for
`_status_marker` to turn into the body. NII פרק ז׳ **סימן ט׳** — the special unemployment
provisions for the war that began 28.2.2026 — is headed by one note and nothing else,
`(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):`, so its sunset window went to
`editorial_notes` and the sign read as though it applied indefinitely. The fallback now
fires only when the note really is a status marker.

| | before | after |
|---|---|---|
| `national-insurance-law-1995/chapter-7/sign-9` body | `סימן ט׳: הוראות מיוחדות … (28 בפברואר 2026)` | same, then a second line `(הוראת שעה מיום 31.3.2026 עד יום 31.3.2027):` |
| its metadata | `editorial_notes: [that label]` | `statutory_notes: [that label]`, no `editorial_notes` |

Of the **119** note-only `law-main` blocks in the capture, **111** are status lines and are
untouched; **1** of the other eight moves (this one). The remaining seven are OpenLaw
speaking in its own voice, unparenthesised — see "Known limits".

**2 (HIGH) — inline temporary substitutions were dropped.** A note reached a body only
from a table cell or a terminating colon, so the identical temporary-order substitution
that לוח ח׳2 keeps inside a cell was deleted from running text.

| row | before | after |
|---|---|---|
| `national-insurance-law-1995/section-340a` (א)(1) | `בשיעור של 6.25% מהשכר` | `בשיעור של 6.25% (בשנים 2025–2026: 7.85%) מהשכר` |
| `…/section-340a` (א)(2) | `בפסקה (1), 1% מהשכר` | `בפסקה (1), 1% (בשנים 2025–2026: 1.8%) מהשכר` |
| `…/section-340a` (ב) | `יהיו 2% מהשכר` | `יהיו 2% (בשנים 2025–2026: 3.6%) מהשכר` |
| `…/section-340` (ד) | `בשיעור 0.4% ממחצית השכר הממוצע` | `בשיעור 0.4% (בשנים 2025–2026: 0.53%) ממחצית השכר הממוצע` |
| `…/section-340` (ה) | `בשיעור 0.1% ממחצית השכר הממוצע` | `בשיעור 0.1% (בשנים 2025–2026: 0.13%) ממחצית השכר הממוצע` |

Surveying the whole capture for the same pattern found two more rows with the same defect,
neither of them cited in the review:

| row | before | after |
|---|---|---|
| `income-tax-ordinance/section-14` (definition of תושב חוזר ותיק) | `…תושב חוץ במשך עשר שנים רצופות לפחות.` | `…עשר שנים רצופות לפחות (לגבי מי שהיה לתושב ישראל בשנות המס 2007–2009, יקראו כאילו נאמר ”חמש שנים רצופות“ במקום ”עשר שנים רצופות“).` |
| `income-tax-ordinance/section-35` (ג) and (ה)(2), three notes | `בתקופת 54 החודשים האמורים,` … `במנין 54 החודשים` … `תחילת תקופת 54 החודשים` | each followed by `(עבור מי שעלה לפני שנת 2022: …)` |

**The survey.** All **2,084** `span.law-note` in the three snapshots were classified under
the old and the new rule: **10 notes across 5 rows** move from `metadata.editorial_notes`
into the body they qualify, **no note leaves a body**, and no row is added or removed
(1,414 before and after). Every gain is exactly a matching loss from `editorial_notes`,
asserted row by row. Rows carrying `statutory_notes` go 148 → 151 and note instances
340 → 350; rows with `editorial_notes` go 353 → 349; `operative: false` stays at 122.
Taking the review's marker list on its own — notes containing `הוראת שעה`, `בתקופה` or a
`במקום` substitution — there are 54 such spans (33 distinct texts): 19 distinct texts were
already in a body and still are, 1 is newly in a body, 0 regressed, and the 13 that stay
out are all `פורסמו תקנות …` / `פורסם צו …` apparatus, where `(הוראת שעה)` is part of the
*title of a cited regulation*, not a statement about the provision.

**3 (MEDIUM) — the release and manifest claims were wrong or stale.** Both sections above
are rewritten: merging publishes (uploads, signs, registers) the release and only
activation is separate, and the manifest is unsigned at this head because this round's
artifact change invalidated the signature added in `3edfd123`.

Six regression tests pin all of this — four over the miniature fixture, which now carries
a sign headed by its window, an inline rate substitution and a re-reading instruction,
each printed next to one of the project's value glosses that must not move; and two over
the committed rows, one for the five substitution rows and one for the three glosses that
stay out (ITO §9א, §47 and §121).

## Checks (run locally on the head of this branch)

- `python -m pytest tests/test_israel_openlaw.py -q` — 91 passed.
- `python -m pytest -q` (full suite) — 4,400 passed, 79 skipped, 208 deselected, 0 failures.
- `ruff check .` — pass.
- `mypy src/axiom_corpus/corpus --ignore-missing-imports` — clean.
- `python -m towncrier build --draft --version 0.0.0` — pass.
- `axiom-corpus-ingest coverage …` — 1,414 provisions against 1,414 inventory entries,
  0 missing, 0 extra, no duplicates.
- `axiom-corpus-ingest validate-release …` — ok, 0 issues, 0 warnings.
- `python scripts/validate_citation_paths.py` — OK, 329,073 records, no new irregular
  families.
- `ops/il-lane/corpus-spotcheck/spotcheck.py` — 73 checks, 0 failures. Eleven of them pin
  this work: the three restored schedules, each rate table's version label, the
  temporary-order substitution, the לוח ח׳2 repeal and expiry markers, ITO §5's repealed
  limbs, that a wholly repealed section still carries `operative: false` (122 rows), that
  no table-free section body is left holding a bare enumerator, and two negative controls —
  OpenLaw's footnote letters and its indexed-amount gloss must stay out of every body.
- The round-2 survey scripts are kept in the lane directory
  (`ops/il-lane/corpus-fix-r2/`): the whole-capture note census, the classification
  dry run, the before/after provision delta, the editorial→body move count with its
  no-loss assertions, and the proof-excerpt re-check.
- The review's `corpus-reproduce.py`, re-pinned to this head, reports 27 table blocks under
  a heading with **none dropped** — לוח ח׳2, לוח י׳ and לוח י״ז render 2,073 / 3,044 / 9,291
  characters where they rendered nothing — the §121 comparison apparatus still dropped, and
  the section-boundary injection probe still 577 → 577 with the injected cross-reference
  retained inside §34.
- Each new test was re-run against the pre-repair adapter loaded from `b4870d37`: every one
  fails there except the deliberate negative control, so none of them is a tautology.
- Every verbatim proof excerpt in the live rulespec-il tree (head `08bc7bc`, which has
  grown since the earlier count of 85) was re-checked against the corpus row it cites,
  before and after this round's change: **145** excerpts, **96** of which cite a row in
  this scope, **90 / 96 match before and 90 / 96 match after, 0 regressed and 0 newly
  matching.** None of the five rows this round changes is cited by any excerpt. (The six
  in-scope non-matches are the pre-existing ones the earlier review documented: historical
  §121 expressions and `schedule-j/sign-1`'s `סך הכל` row. The other 49 excerpts cite
  `il/policy/…` and the National Health Insurance Law, which are outside this scope.)
- Re-running the canonical extract command reproduces the committed artifacts byte for
  byte.
