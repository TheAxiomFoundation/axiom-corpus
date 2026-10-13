# Opt-in eCFR appendix ingestion

The eCFR inventory and extraction commands include parts, subparts, and sections
by default. Add `--include-appendices` to both commands when a new ingestion run
should also contain supported part and subpart appendices:

```bash
axiom-corpus-ingest inventory-ecfr --base /tmp/ecfr-604 \
  --version 2026-08-30 --as-of 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices
axiom-corpus-ingest extract-ecfr --base /tmp/ecfr-604 \
  --version 2026-08-30 --as-of 2026-08-27 \
  --only-title 45 --only-part 604 --include-appendices
```

Use a separate run/version when changing the intended scope of an existing
artifact. These commands write local artifacts; publication is a separate step.
The Python functions `build_ecfr_inventory`,
`build_ecfr_inventory_from_structures`, `iter_ecfr_title_provisions`, and
`extract_ecfr` expose the same keyword, `include_appendices=False` by default.

Traversal preserves source order without converting a provision twice.

## Part appendices

A part appendix names its part. Its parent is the part row, at level 1, wherever
it sits in the part: directly, in a subject group, or inside a subpart.

| eCFR identifier | Citation path |
| --- | --- |
| `Appendix A to Part 604` | `us/regulation/45/604/appendix-a` |
| `Appendix 12 to Part 604` | `us/regulation/45/604/appendix-12` |
| `Appendix II to Part 200` | `us/regulation/2/200/appendix-ii` |
| `Appendix to Part 720` (unnumbered) | `us/regulation/5/720/appendix` |
| `Appendixes to Part 50` (a collective note) | `us/regulation/10/50/appendixes` |

Designators follow the subpart-appendix grammar below: a number, a single letter,
or an uppercase roman numeral, lowercased in the path. The legal identifier reads
`2 CFR part 200, appendix II` (`5 CFR part 720, appendix` and
`..., appendixes` for the unnumbered and collective forms). The eCFR of 2026-10-08
has no live collective part appendix; the form is accepted so that part and
subpart appendices share one grammar.

Part appendices sort after the part's sections and subparts, by the subpart rule
below with the part as the container: when the part's lettered designators are
all roman numerals and one has more than one character, they are numerals and
sort by value (2 CFR 200's Appendices I–XII sort 1–12); otherwise a letter sorts
by `ord` and a number by its value. An unnumbered or collective appendix sorts at
1,000,000: before every letter, numeral and number above 0, and tied with an
`Appendix 0`, which the citation path then orders. Only part appendices that sit in the part they name
count toward its classification; reserved ones count. A multi-character designator
among letters (`II` beside `A`) fails validation.

A number, or a letter among letters, keeps exactly the path, ordinal, legal
identifier, identifiers and metadata it had before roman and unnumbered part
appendices were supported: its metadata carries `appendix` (the lowercased
designator) and `appendix_identifier` and no `appendix_numbering`. A roman-numbered,
unnumbered or collective part appendix also carries `appendix_numbering` (`roman`,
or null), from which a structure-only placeholder takes its ordinal. One designed
exception: a live single letter (`I`, `V`, `X`, `L`, `C`, `D`, `M`) in a part whose
other lettered appendices are roman numerals, including a reserved multi-character
one, reads as a numeral. No eCFR part had that shape on 2026-10-08.

Part appendix identifiers are matched ASCII-only, as subpart appendix identifiers
are. Case-insensitive matching used to admit look-alikes and read them by Unicode
case folding: the Kelvin sign as `appendix-k`, a dotless `ı` as `appendix-ı`, which
the citation-path grammar rejects. Such identifiers, and a no-break space between
words, now fail validation. No eCFR appendix identifier of 2026-10-08 contains a
non-ASCII character other than `§`, and none of those parse as part appendices.

The eCFR title structures of 2026-10-08 list 1,588 nonreserved part appendices with
a number or single letter, which the adapter already parsed, and 82 roman-numbered
ones in 28 parts and 60 unnumbered ones, which it parses now. With
`--include-appendices`, 80 more parts pass inventory validation. The other 8 parts
with roman or unnumbered appendices still fail on another node in the part: `Figure 1 to Part 1213`, `Table 1 to Part 150`, `Policy Statement to Part 145`,
`Figures to Part 38`, `Appendix I(F) to Part 13`, or a nonreserved
`Appendix IV to Part 261 [Reserved for Radioactive Waste Test Methods]`.

## Subchapter appendices

An appendix to a subchapter sits in that subchapter's last part on the eCFR. 41 CFR
chapter 101's `Appendix to Subchapter D` is in part 101-21, at reader path
`.../subchapter-D/part-101-21/appendix-Appendix%20to%20Subchapter%20D`, and on
2026-10-08 it is the only live one in all 49 titles (three more in title 41 are
reserved). It is read only inside the subchapter it names; one that names another
subchapter fails validation. The part that holds it is its parent, at level 1, and
the path segment names the subchapter, so it never takes a part appendix's path:

| eCFR identifier | Citation path | Legal identifier |
| --- | --- | --- |
| `Appendix to Subchapter D` (in part 101-21) | `us/regulation/41/101-21/appendix-to-subchapter-d` | `41 CFR chapter 101, subchapter D, appendix` |

It sorts with unnumbered appendices (ordinal 1,000,000). Metadata carries
`appendix_subchapter`, `appendix_identifier`, `appendix: null` and
`appendix_numbering: null`, and identifiers add `ecfr:subchapter`. A designated
form (`Appendix A to Subchapter D`) has no live instance and stays unsupported.

## Subpart appendices

Supported subpart appendix identifiers name the subpart and the part. Their parent
is the subpart row, at level 2:

| eCFR identifier | Citation path |
| --- | --- |
| `Appendix II to Subpart C of Part 404` | `us/regulation/20/404/subpart-C/appendix-ii` |
| `Appendix 1 to Subpart P of Part 404` | `us/regulation/20/404/subpart-P/appendix-1` |
| `Appendix A to Subpart C of Part 910` | `us/regulation/2/910/subpart-C/appendix-a` |
| `Appendix to Subpart B of Part 404` (unnumbered) | `us/regulation/20/404/subpart-B/appendix` |
| `Appendixes to Subpart C of Part 404` (the note before a subpart's appendices) | `us/regulation/20/404/subpart-C/appendixes` |

A designator is a number, a single letter, or an uppercase roman numeral, and the
path segment lowercases it (`Appendix a ...` and `Appendix A ...` are the same
appendix, and classify the same way). The legal identifier reads
`20 CFR part 404, subpart C, appendix II` (`..., appendix` and `..., appendixes` for
the unnumbered and collective forms). Metadata carries `subpart`, `appendix` (the
lowercased designator, or null), `appendix_identifier` and `appendix_numbering`.

Appendices sort after their subpart's sections (ordinal 1,000,000 plus the
designator's value). Whether `I` and `V` are numerals or letters depends on the
other appendices of the same subpart: when every non-numeric designator is a roman
numeral and one has more than one character (`I`, `II`, ... `VII`), they are
numerals and sort by value; otherwise single letters keep the part-appendix ordinal
(`ord` of the letter). A multi-character designator among letters (`CC` beside
`A`) has no unambiguous order and fails validation. Only appendices that sit in the
subpart they name count toward its classification, so a misplaced appendix, selected
or not, never changes how its named siblings sort; reserved appendices do count.
`extract-ecfr` classifies designators from the retained structure, so a
structure-only placeholder and the XML record it stands in for get the same
ordinal; an appendix that only the XML has is outside the inventory and is not
taken.

A subpart appendix must sit inside the subpart and part it names. One that does
not (for example `Appendix A to Subpart F of Part 2520`, which the eCFR places
outside any subpart) fails validation, as a part appendix that names another part
does.

Opted-in inventory construction rejects unsupported nonreserved identifiers,
including hyphenated, alphanumeric or lowercase multi-character designators
(`Appendix D-1 to Part 208`, `Appendix M1 to Part 226`, `Appendix A-1 to Subpart I
of Part 550`, `Appendix C1 to Subpart B of Part 430`, `Appendix ii to Part 604`), a
collective note with a designator (`Appendixes A to Part 604`), hyphenated parts
(`Appendix to Part 60-20` in title 41; the adapter skips those parts' sections too), identifiers that cite the title (`Appendix B to Subpart A of 10 CFR Part
51`, `Appendix to 19 CFR Part 0`), and nodes that are not appendices to a part or
subpart (`Figure 1 to Part 1213`, `Appendix A to Chapter I`). A parsed part that
contradicts the enclosing part also fails validation. These errors do not imply full appendix coverage.
Exact `--section` selectors exclude appendices before validation. The lower-level
iterator likewise applies an explicit citation allowlist before converting an
appendix; selected unsupported identifiers still fail closed.
Appendix validation errors (`EcfrAppendixError`, a `ValueError`) from either CLI
command print a diagnostic to stderr and exit with status 2 before writing run
artifacts; an existing run is preserved. That holds for contradictions only the XML
shows, too, in multi-title runs as well: before writing anything, `extract-ecfr`
reads or fetches every pending title's XML (staging fetched XML outside the corpus
base, so it is fetched once) and converts its selected appendices in memory; it
writes sources, images, structures, inventory, provisions and coverage only after
every title passes. A title whose XML cannot be fetched there is reported as a title
error and is not extracted, so no unchecked XML reaches the run. Other parsing or
I/O failures can still occur after source capture and surface as title errors.

For included appendices, extraction archives official PNG bytes for source
images, retains image references in the body, and keeps HD1–HD3 heading text.
Image-only forms therefore retain a nonempty body pointing to the captured
source. Existing SHA-256-bound formula transcription checks still apply. Image
references are source evidence, not OCR text or an executable formula.

Appendix bodies also keep table captions, as a block before the table's rows
(`Table No. 1—Residual Functional Capacity: ...` in appendix 2 to subpart P of
part 404), and read a `<br/>` as a word break, so `means<br/>less` is
`means less`, not `meansless`; adjacent block children (`P`, `FP`, `PSPACE`, `HED`,
`HD1`–`HD3`, `LI`, `DIV`) separate words the same way, while inline markup still
joins (`FEV<sub>1</sub>` is `FEV1`). An appendix's own bracketed source note
(`CITA`) is not kept, and neither is plain text that sits directly in an element the
renderer does not read, such as an editorial cross-reference (`XREF`, "Link to an
amendment published at 91 FR 40836, July 2, 2026."); paragraphs, headings and tables
inside such an element are still kept, and text nested inside a kept element (a
caption, a paragraph or a table cell) is kept whatever its tag. These rendering changes apply
to part appendices as well, whose path, parent, level, ordinal and metadata are
unchanged; no locked part appendix has a caption, a `<br/>` or adjacent block
children. Section rendering is unchanged: it still drops table captions and joins
words across `<br/>`.

When an inventory lists a supported appendix absent from the retained XML,
the existing structure-only fallback preserves its source identity with
`body=None`, `structure_only=True`, and `body_status=not_in_ecfr_full_xml`.
Inventory coverage alone does not imply that every provision has extracted text.

The offline recovery scripts `scripts/recover_ingest.py` and
`scripts/recover_ingest_batch.py` support section-only eCFR recovery. They cannot
replay an appendix-enabled run's inventory scope and archived graphics. Both
refuse `include_appendices: true`, appendix citations (including descendants) in
`covers_citation_paths`, or replacement of a destination inventory containing
appendices. This preflight runs before artifact writes, including in dry runs;
the batch also checks before reusing a previous success report and aborts without
rewriting that report. XML containing excluded appendices remains valid for
ordinary section-only recovery. Preserve appendix artifacts and use an
appendix-aware inventory/extraction workflow for a separate run instead; these
recovery scripts do not certify an appendix replay as complete.

Ordinary section rendering and formula-only image capture retain their prior
behavior, even in an appendix-enabled run. This change does not add HD1–HD3 text
or non-math image capture to sections. It also does not repair the inherited
loss of a nested `MATH` marker inside a consumed paragraph, table, or heading;
standalone `MATH` transcription and markers remain supported.

The retained 20 CFR 416 source remains a 622-entry inventory by default, and its
approved 14-record deeming slice reproduces the prior producer's bytes. The
[baseline manifest and replay instructions](validation/us-cfr-416-deeming-baseline.md)
distinguish that replay from the older published July provisions file.
