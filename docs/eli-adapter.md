# ELI adapter

`extract-eli-documents` ingests acts exposed through the European Legislation
Identifier (ELI) model. Denmark's official `retsinformation.dk` service is the
phase-1 reference host.

The adapter reads the ELI `LegalResource`, `LegalExpression`, and `Format`
nodes. It records `in_force`, `consolidated_by`, `changed_by`, `consolidates`,
`title`, `title_short`, `title_alternative`, `date_document`,
`responsibility_of`, and XML/HTML/PDF manifestation URLs and their
`legal_value`. These graph facts are copied into every normalized provision's
metadata as the mechanical amendment-diligence trail.

Before downloading the structured text, the currency gate refuses an act when
`in_force` is `notInForce` or `consolidated_by` names a successor. Use
`--allow-superseded` only for an intentional historical ingest.

For Denmark, the adapter routes LexDania `Dokument/DokumentIndhold` XML from
the shape of the direct `DokumentIndhold` children. It supports three shapes:

- Consolidations contain the ordinary paragraph structure. In the current
  pack their direct wrappers are `Indledning`, `Bog`, and `Ikraft`; direct
  `Paragraf`, `Afsnit`, and `Kapitel` roots are also supported. After this
  shape is selected, every descendant `Paragraf` becomes one level-2 corpus
  provision through the original paragraph extractor.
- Amendment acts contain a `Hymne` preamble followed by direct
  `AendringCentreretParagraf` and `IkraftCentreretParagraf` units. Each direct
  centered unit becomes one provision in document order. Its label combines
  the literal element name and `localId`, for example
  `aendringcentreretparagraf-1` or `ikraftcentreretparagraf-8`, and its body is
  the complete normalized `itertext` of that unit.
- Prose documents have direct children drawn only from `Resume` and
  `TekstGruppe`, with at least one `TekstGruppe` and at most one `Resume`.
  `Resume` becomes a level-2 `resume` provision when present, and
  the `TekstGruppe` paragraphs in document order always become one level-2
  `tekst` provision. Their citation paths append `/resume` and `/tekst` to the
  level-1 document root.

Prose wrapper bodies preserve each supported direct child (`Exitus` or
`Rubrica`) as a paragraph. Non-table paragraphs use normalized `itertext`; this
also preserves the `Index` lists observed in the principle-notice fixture.
Paragraphs are joined with `\n\n`. An empty `Exitus` is a paragraph break, and
consecutive empty elements collapse so bodies have no repeated, leading, or
trailing empty breaks. A `Rubrica` with empty or whitespace-only text fails
closed. For a `Table`, the normalized text of the actual cells in each `Tr` is
joined with ` | `, and rendered rows are joined with `\n`; `colspan` does not
synthesize extra cells.

The adapter may additionally recognize these exact, case-insensitive whole-
paragraph `TekstGruppe` headings, which are the closed vocabulary observed in
the principle-decision prose fixtures:

- `1. Baggrund for at behandle sagen`
- `2. Reglerne`
- `3. Andre Principafgørelser`
- `4. Den konkrete afgørelse`
- `Baggrund for at behandle sagerne principielt`
- `Reglerne`
- `Love og bekendtgørelser`
- `Praksis`
- `De konkrete afgørelser`

Every direct `Rubrica` in a `TekstGruppe` is an explicit heading, independent of
that closed vocabulary. Its normalized text is converted with the existing
citation-safe LexDania slug rule, including Danish-letter transliteration; for
example, `Landsskatterettens afgørelse` becomes
`tekst/landsskatterettens-afgoerelse`. A heading that cannot produce a slug
fails closed.

Each explicit `Rubrica` or matched `Exitus` heading emits a level-3 child of
`tekst`. Its citation path is `<root>/tekst/<heading-slug>`, such as
`<root>/tekst/reglerne`; numbered heading slugs retain their number, such as
`tekst/2-reglerne`. Its body starts with the heading paragraph and continues up
to, but not including, the next heading of either kind. Text before the first
heading remains only in the complete `tekst` provision. The complete `tekst`
provision is always emitted, so citation coverage never depends on heading
recognition. Repeating a matched heading, or producing the same final heading
slug from any two headings, fails closed instead of adding an ordinal suffix.

A `Paragraf` nested inside a centered unit is replacement text destined for
the act being amended. It is therefore retained inside the centered unit's
body and is not emitted as a standalone provision of the amending act. This
keeps the operative instruction and its replacement text together.

Before routing, the adapter requires whitespace-only `DokumentIndhold.text`
and direct-child tails. It fails closed on any mixture of standard, centered,
and prose direct elements, any unknown direct element, duplicate `Resume`
wrappers, or a shape without an operative unit. Within `Resume` and
`TekstGruppe`, any direct element other than `Exitus` or `Rubrica` also fails
closed. `Hymne` is accepted only as the centered-act preamble. Errors name the
XML title and root ID; manifest extraction adds the source ID, ELI, and manifest
title. Wrapper attributes such as the `id` values found in newer LexDania prose
documents do not participate in routing.

On the consolidation path, `Paragraf@localId` supplies the paragraph number,
including letter suffixes such as `1a`; `Explicatus` supplies the displayed
section label; and child `Stk` elements are concatenated in document order.
The surrounding `Afsnit` and `Kapitel` `localId` and `Explicatus` values are
retained as block metadata. The manifest's citation path is the root document
path and section paths append citation-safe labels such as `paragraf-1-a`.

Paragraph labels are resolved after every `Paragraf` in an act has been built.
Labels that occur once retain that exact shape. When a paragraph label repeats,
every instance is prefixed by its outer-to-inner structural chain: numbered
`Afsnit` and `Kapitel` components produce labels such as
`afsnit-2-kapitel-4-paragraf-29`, while a paragraph in an `Ikraft` block uses a
label such as `ikraft-paragraf-29`. If those structural labels are still not
unique (for example, two paragraph 29 elements in the same afsnit and chapter),
extraction fails instead of dropping a provision or adding an ordinal suffix.
This collision path remains for consolidations and its synthetic collision
fixtures; amendment acts route to direct centered units before nested
replacement paragraphs can reach it.

## Denmark pack regression baseline

The 64-document Denmark campaign pack contains 13 consolidations and 51
centered amendment acts. The consolidation route produces 1,285 paragraphs;
the centered route produces 573 units (501 amendment and 72 commencement),
for 1,858 blocks and 1,922 root-inclusive provision rows.

The consolidation guarantee is scoped to the 13 true consolidations. A pack
audit compares every full section list with `origin/main` before computing the
digest. Each row below pins the compact, sorted, UTF-8 JSON SHA-256 of that
file's complete section list:

| XML | Sections | Section-list SHA-256 |
|---|---:|---|
| `lta-2019-63` | 44 | `2348ad640b6f78635f14e2a67606078f6cac676720cfe951b128bef869453e34` |
| `lta-2020-121` | 9 | `6450b1b80de62b252db5e75190f356e2b43bf5e9642246d8b019c65582415e7e` |
| `lta-2021-1284` | 34 | `9f1bbde03691fce7bdb569c639c518f5f1faa2e88c36066d55b25775cc6a9d1b` |
| `lta-2022-724` | 23 | `980937bf85d2cfc5af8444048372be2f4c36c23c32ab85054be9ca5620a41f4b` |
| `lta-2023-395` | 92 | `0e84d77fb561c2d58ae44a2bd767ab0ce06c97a5fff5912d3f118db9b7a27447` |
| `lta-2024-460` | 146 | `81adde61f5ef810675186b383385d9c75687bf98f0510bb30fcb204d73404472` |
| `lta-2024-1123` | 164 | `b8b88a41fdd8f33fb63ac7ea58873ba1293307724c0aa66e696e7eab946a839a` |
| `lta-2024-1142` | 122 | `ec77cad2b32d3949308ad36cfaacc7174be8ae38f71b5b1f8157f3fb73a0089a` |
| `lta-2024-1243` | 121 | `374cb1ebdb39fb473e3b7c1be79b41738611b068e3e091e4b7c3bda5f8dbbe3d` |
| `lta-2025-603` | 24 | `ca10943ee7f804a10b3cb34fcd603fd59316ce1b56ee56260ef4db187e4c01e5` |
| `lta-2025-1004` | 186 | `4d8979ce8d86aa38d92b54d2a57c5e8cafdd8aae718c0b416ede539b2b84ed26` |
| `lta-2025-1077` | 149 | `af7de61ac75894e2312911dc67ef3e408ac13f6e1330096482eaeb5bedbe785f` |
| `lta-2025-1500` | 171 | `a9c003bb8d8e735ca5766bb166c2bcc7cdcd28fb719e7eff306b05a62d0c4b91` |

Hashing the numerically ordered compact JSON rows
`(stem, section_count, section_list_sha256)` produces the aggregate digest
`ff2bd3cc9056ac1d7f0e2ef50336d170e25237bace1a8b3be4d11987a6f838cc`.

Phase 1 supports structured XML extraction. Entries requesting PDF, or graphs
without an XML manifestation, receive an error directing them to
`extract-official-documents`, which remains the PDF fallback. A Belgium/Justel
host profile is future work; the existing Belgian adapter handles its current
HTML-specific workflow.
