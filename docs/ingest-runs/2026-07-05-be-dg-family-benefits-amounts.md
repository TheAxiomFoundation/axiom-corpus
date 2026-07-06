# Belgium DG family-benefit amounts re-ingest reasoning

Impact basis:

- axiom-corpus issue 205 records that the German-speaking Community (DG) family-
  benefit decree of 23 April 2018 (numac 2018202523) was ingested such that its
  amount-bearing articles do not carry the amounts in resolved provision text.
  In the `2026-07-01-be-dg-family-benefits` version the amount container
  provisions (`.../family-benefits`, `.../family-benefits-current`) have
  `body: null`, and the text-bearing `.../family-benefits/block-1` (77 KB German
  moniteur) contains the article structure but **zero euro amounts** (EUR = 0,
  euro-comma tokens = 0). `rulespec-be/be-dg/statutes/family_benefits/amounts.yaml`
  cites this decree for every DG monetary value (base 157, annual supplement 52,
  large-family 135, social 75, disability categories 85/112/262/432/491/526/561,
  orphan 239/120, birth/adoption 1144) and quotes German spans such as "Art. 8 -
  Basiskindergeld Die Regierung gewährt ein Basiskindergeld, das 157 Euro pro
  Monat beträgt" — but those spans were not text-verifiable against the cited
  corpus provision.

Root cause:

- The original ingest used `extract-official-documents`, which collapsed the
  whole German-language Moniteur publication into one document-level block with
  the euro amounts stripped. The amounts ARE in the official source: the German
  original Moniteur publication of 12 June 2018
  (`article.pl?language=de&sum_date=2018-06-12&numac_search=2018202523`) contains
  "157 Euro pro Monat", "52 Euro pro Jahr", the seven "Kategorie N: … Euro"
  supplements, the "Geburtsprämie … 1.144 Euro", etc. The defect was extraction
  granularity, not a missing source.

Parser fix (corpus adapter):

- The `belgian-eli` Moniteur article-heading segmenter
  (`_MONITEUR_ARTICLE_HEADING_RE`) only matched French/Dutch headings terminated
  by a period ("Art. 8."). German-language DG publications use a dash instead
  ("Art. 8 - Basiskindergeld", "Artikel 1 - …"), so the German text fell through
  to a single flat document provision — exactly the shape issue 205 reports. The
  regex now also accepts the `Artikel` keyword and a `" - "` dash terminator, so
  German DG statutes segment to the article level. Existing French/Dutch matching
  (period terminator) is preserved; a focused regression test
  (`test_parse_belgian_eli_moniteur_german_article_headings_segment_with_amounts`)
  pins the German behaviour, and the full belgian-eli suite passes.

Official sources (both genuine ejustice captures, article-segmented):

- **German-language original Moniteur publication of 12 June 2018** — 118
  article-level provisions. This is the authentic German-language expression for
  the German-speaking Community and carries the base (2019) amounts rulespec
  cites and quotes:
  - Art. 8 Basiskindergeld = 157 Euro pro Monat
  - Art. 15 Jahreszuschlag = 52 Euro pro Jahr
  - Art. 17 large-family supplement = 135 Euro pro Monat
  - Art. 19 Sozialzuschlag = 75 Euro pro Monat
  - Art. 21 disability categories = 85 / 112 / 262 / 432 / 491 / 526 / 561 Euro
  - Art. 23 / 25 orphan supplements = 239 / 120 Euro
  - Art. 30 / 34 birth / adoption premium = 1.144 Euro
- **French-language consolidated Justel text** — 126 article-level provisions,
  the in-force consolidated (uprated) expression: Art. 8 = 157 euros (unchanged),
  Art. 17 = 137,50, Art. 19 = 77,50, Art. 21 categories =
  87,50/114,50/264,50/434,50/493,50/528,50/563,50, Art. 23/25 = 241,50/122,50,
  Art. 30/34 = 1 144 euros. Grounds the current consolidated amounts alongside
  the German base values.

Both expressions share the numac but land under distinct `citation_path`
document-types (German `decreet` vs French `decret`), so the 244 provisions carry
no path collisions (verified: 0 duplicate citation_paths). Both are scoped to
jurisdiction `be-dg` via the manifest `jurisdiction` override so rulespec proof
atoms ground in the DG namespace.

Verification (corrupt-a-digit standard):

- All nine rulespec base amounts are present verbatim in the German article
  bodies (157/52/135/75/[85-561]/239/120/1.144/1.144); the German Art. 8 body is
  the exact rulespec span. The French consolidated bodies carry the in-force
  amounts per article. The euro figures are present as amounts, not as
  cross-references to other articles.

Citation-path ratchet:

- `schema/citation-path.v1.json` `uppercase_segments` raised 1346 → 1348 for the
  two genuine Justel future-law status labels `article/38-DROIT-FUTUR` and
  `article/76-1-DROIT-FUTUR` (Art. 38 indexation modalities, Art. 76/1
  prescription delay — real provisions carrying substantive text), the same
  category as the study-allowance `article/9-TOEKOMSTIG-RECHT` bump in #218. The
  schema note now records the Justel future-law status suffix.

Source-HTML storage:

- Both source HTML files (German Moniteur, French Justel) are committed to git
  (Belgian ejustice HTML carries no `EffectId="key-…"` tokens and trips no
  push-protection secret pattern; verified 0 matches), matching the study-
  allowance (#218) precedent.

Note on scope / rulespec follow-up:

- This ingest makes the amounts text-verifiable at article granularity, resolving
  the corpus-side defect. rulespec-be's proof atoms currently anchor to the old
  flat `.../family-benefits/block-1` path; they can now re-anchor to the article-
  level paths (`be-dg/statute/decreet/2018/04/23/2018202523/article/8` for the
  German span) so each amount spans the exact article stating it — the rulespec-
  side change is separate from this corpus ingest.
