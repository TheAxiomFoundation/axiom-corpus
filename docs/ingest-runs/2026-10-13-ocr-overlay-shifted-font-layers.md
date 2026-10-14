# OCR overlay: decoding shifted-font layers (2026-10-13)

With `ocr: true`, `documents.py::_pdf_page_text` reads a scanned PDF page by Tesseract when
its text layer is only an overlay, and merges in the layer lines OCR did not read (PR #868,
`docs/ingest-runs/2026-10-13-ocr-overlay-layer-lines.md`). A span holding a control
character is a garbled font's, and #868 leaves it out, with every span of its font on the
line. On CMS state-plan forms many typed dates, names and notes are in such fonts, and
they are not garbage: their character codes are a constant shift from ASCII. This change
decodes them where the page itself shows the shift, and measures it on the same 1,041
pages #868 measured.

Nothing was published, loaded or activated, and no merged scope was edited.

## The defect

Reproduced from retained bytes with #868's code at `8a2452fea`:

- Typed values OCR did not read are dropped as garbled.
  `us-or/policy/cms/medicaid-state-plan/spa/or-15-0006/approval-document/page-3` loses
  "11/30/15", "12/10/15" and "12/01/15". MA-20-0024 page 3 loses "09/30/20". OR-19-0002
  page 3 loses two notes ("5/28/19-State authorized a P&I change to blocks # 8 and 9"), four
  dates and the signer "David L. Meacham". WA-14-0003 page 3 loses its P&I note, two dates
  and the signer's name and title.
- A garbled line without a control character is appended as text: AL-20-0004 page 4
  "1(:" ("NEW"), MA-20-0024 page 3 "%JSFDUPS" ("Director"), WA-19-0012 page 3 "%FQVUZ %"
  ("Deputy D").

## Why the codes are shifted

Read from the PDFs themselves:

- The fonts are Type0 fonts with Identity-H codes and no ToUnicode map: MinionPro-Regular
  (CIDFontType0 with a CIDFontType0C program, e.g. WA-19-0012) and Arial, ArialMT and
  TimesNewRomanPSMT (CIDFontType2 with CIDToGIDMap /Identity, AL-20-0004 and OR-15-0006).
  The codes are glyph ids (PyMuPDF's text trace reports the same numbers as glyphs).
- MuPDF has no Unicode for these characters. With TEXT_CID_FOR_UNKNOWN_UNICODE (part of
  `fitz.TEXTFLAGS_TEXT`, which `_pdf_page_text` uses) it prints each character's code;
  without the flag it prints U+FFFD.
- On these forms the codes are 31 below ASCII in Minion Pro ("\x01" is a space,
  `"DUJOH\x01%FQVUZ\x01%JSFDUPS` is "Acting Deputy Director") and 29 below in Arial and
  Times New Roman (`-DPHV\x03*\x11\x036FRWW` is "James G. Scott").

Three things the PDFs show rule out decoding a whole font name by one shift:

1. **Names are shared.** AL-20-0004 page 4 has three fonts named ArialMT, and an Arial.
   One ArialMT has a ToUnicode map and writes the digital signature ("Digitally signed by
   Anne M. Costello -S"). It shares its CIDFont with an unmapped ArialMT. NV-20-0002 page
   3 writes "March 13, 2020" in an unmapped Minion Pro (no ToUnicode), except the "3",
   which MuPDF maps. The page has a second Minion Pro, with a ToUnicode map, and spans of
   both are named MinionPro-Regular. A shift applied by name would garble the mapped text.
2. **MuPDF segments the two reads differently.** On 43 of the 1,041 pages, the read with
   the flag and the read without it break the characters into different spans and lines.
   So characters are matched by where they are drawn (origin, and order at that origin),
   not by position in the output.
3. **A Type 3 font can be only partly unmapped.** When MuPDF does not know a glyph
   name, it prints a printable code as itself, as if mapped. Only the control codes then
   show as unmapped, and MuPDF can put them in spans of their own. A synthetic Type 3 font
   31 below ASCII shows it: in "Acting Deputy Director" only the spaces read as U+FFFD.

The "+1" signature strings are a different thing. ID-20-0001 page 3 has "Ejhjubmmz!tjhofe!cz!Svui!B/!Ivhift" for "Digitally signed by
Ruth A. Hughes", and MO-20-0016 page 3 has the like. They are in a non-embedded Helvetica
with WinAnsiEncoding, which maps every code. On ID-20-0001 the page's one font object also
writes the correct "CheckOne)" and "Transmittal". So neither a per-font nor a
per-character signal separates the shifted strings, and they are not decoded; #868
appends none of them. OCR reads the signers' names. What is lost is, on each page, the
"Digitally signed by ..." line and the date line ("Date: 2020.06.30 16:47:42 -05'00'",
"Date: 2020.08.03 13:21:20 -05'00'").

## The rule

On a page whose layer `_pdf_page_text` merges with non-blank OCR text, and whose `dict`
spans hold the text output's characters (#868's `_same_layer_characters`),
`_pdf_decoded_span_lines` runs after #868's `_with_layer_marks` and before
`_without_garbled_spans`:

1. **Unmapped characters** (`_pdf_unmapped_characters`, `_pdf_unmapped_status`): those
   printed as U+FFFD by a second `rawdict` read without TEXT_CID_FOR_UNKNOWN_UNICODE,
   paired with the first read's characters by origin and order at that origin, and not
   U+FFFD in the first read. Where the reads draw a different number of characters at an
   origin, or mapped and unmapped ones together (whose order they need not share), the
   characters there are unknown. The characters come from the `rawdict` read with the
   page's flags and sort, whose spans must be the `dict` spans exactly; otherwise nothing
   is decoded.
2. **Which fonts may be decoded** (`_pdf_undecodable_fonts`). Spans name fonts, not font
   objects, so a font name is decoded only when exactly one font object the page's text
   can be drawn in carries it (`_pdf_font_objects`).
   - **Finding the fonts** (`_pdf_drawn_font_xrefs`). The walk starts from the page's
     resources (inherited from the page tree when it has none) and from every annotation
     in its /Annots, whatever the subtype. It goes through Resources/Font and on into
     forms and tiling patterns. From Resources/ExtGState it follows every reference: a
     font is counted (its /Type resolved when indirect), and a stream is walked as a
     holder with its dictionary's references followed too, since a soft mask written as
     a stream holds its group in /G (review round 4). MuPDF extracts text from all of
     those. `get_fonts` lists only the fonts of
     the page and its forms, and `annot_xrefs` skips annotations of a subtype it does not
     know (review round 3).
   - **Naming them** (`_pdf_font_names`, checked on PyMuPDF 1.26.7 and 1.28.2). A font's
     span name is its /BaseFont. For a Type0 font it is the descendant's /BaseFont, not
     the Type0 font's own, which can end in -Identity-H; for a Type 3 font it is its
     /Name, direct or indirect. The name is cut to 31 bytes, read as Latin-1, and
     stripped of a six-letter subset prefix (review round 4: a Type 3 name is cut too).
     A Type 3 font without a name is "Unnamed-T3" under 1.26 and "Type3 (<n> 0 R)" under
     1.28; both are counted.
   - **How far the naming reaches.** It explains every span font name on 1,040 of the
     1,041 pages (`scripts/font_identity_probe.py`, `evidence/font-identity-probe-r3.json`).
     The other is a font MuPDF substitutes, OH-19-0025 page 3's "NimbusSans-Regular",
     which has no unmapped characters. A name that no object explains is not decoded.
   - **When the fonts can't be known for certain, nothing on the page is decoded.** That
     covers:
     - a font, a Type0 font's descendant or an annotation written inline (a Type0 font's
       /DescendantFonts must be exactly one reference);
     - a /Subtype, /BaseFont or descendant that is not written as a name in the font's
       dictionary (MuPDF resolves `/BaseFont 70 0 R` to the name it refers to, while the
       bare key gives "70 0 R");
     - a reference printed with a generation other than 0, or to an object the file does
       not have;
     - anything PyMuPDF can't read;
     - a page without resources more than 64 page-tree nodes below the node that has
       them;
     - more than 4,096 distinct holders and graphics-state objects to walk (an object
       met twice counts once).

     None of these is an error: the page is read as #868 reads it.
   - **The font object itself** must be a Type0 font, whose codes are CIDs. Its /W array
     must give a width for every code it draws unmapped on the page, and leave some code
     between the least and greatest of those without one (below). It may be a font that
     only an annotation's appearance draws.
   - **Per line,** a font's characters are candidates only when every one of them there is
     unmapped, MuPDF's own spaces (U+0020) aside.
3. **A shift k** reads code c as chr(c + k), and only into printable ASCII, U+0020 to
   U+007E (`_pdf_decoded_layer_line`).
4. **Evidence** for font f and shift k (`_pdf_font_code_shifts`): a line whose candidate
   characters are all f's, decoded by k, that the OCR text reads (#868's
   `_ocr_read_line`), with at least 4 letters or digits among the decoded characters.
   Font f's shift is k when no other shift has evidence for f, and k's distinct evidence
   lines, each counted once at the most decoded letters or digits any line decoding to it
   has, hold at least 8 of them: at least 4 distinct, from at least two of digits,
   capitals and small letters. Shift 0 (codes that are the text) counts as a rival but is
   never applied.
5. **Decoding.** A line is decoded only when every unmapped or unknown character in it can
   be, in every span, into printable ASCII, and no span of it still holds a control
   character once decoded. Otherwise it is left as read. Such a span would be a mapped
   font's whose map gives a control character, as a Type 3 glyph named uni0016 does;
   `_without_garbled_spans` would leave that span out, and the line would be a fragment
   (review round 3). One value can
   run across fonts: AL-20-0004 page 4 writes "03/01/2020" as "0" and "/01/2020" in Arial
   and "3" in ArialMT, and decoding Arial alone left the fragment "0 /01/2020". Each
   decoded character is decoded one for one. Every other character, and every span's
   paint and font, is unchanged. The decoded spans no longer hold control characters, so
   `_without_garbled_spans` keeps them, and #868's merge appends the lines OCR did not
   read.

### Fonts that number their glyphs in order of use

A shift learned from the lines OCR read is applied to glyphs it has not seen. That is right
for a font whose codes keep the glyph order of the font it was cut from, and wrong for one
that numbers its glyphs in the order a document first uses them: such a font can fit one
shift wherever its evidence glyphs were first used in steps that match their ASCII
distances. The class rule stops the short cases (review round 1: "1234" and "1122" at codes
0-3, four glyphs of one class) but not a run that bridges two classes through the
punctuation between them (review round 2: a font whose first eleven glyphs are
"89:;<=>?@AB", read by OCR with "8899AABB", would read its twelfth glyph, "x", as "C").

Nothing in these fonts' own programs says which character a glyph is: every shifted
Minion Pro is CID-keyed CFF, which carries no glyph names, and the Arial and Times New
Roman subsets have neither a cmap nor glyph names (`scripts/font_program_probe.py`,
`evidence/font-program-probe.json`). Their /W arrays tell the two numberings apart, read
the right way.
- **Order of use.** A font numbering glyphs in order of use has a glyph for every code
  from its first to its last. So between the least and greatest code it draws on a page,
  every code has a glyph, and a /W that gives each drawn code a width leaves none of them
  without one.
- **Original order.** A font that keeps an original glyph order lacks, in that range, the
  glyphs its subset left out.
- **A gap elsewhere says nothing** (review round 3): .notdef at code 0, below codes
  numbered from 0xE000, leaves one.

All 16 shifted fonts found are single Type0 objects (`scripts/width_probe.py`,
`evidence/width-probe.json`). Each /W lists 10 to 55 codes between 1 and 92, and gives
every code the font draws unmapped on its page a width. Between the least and greatest
of those codes, it leaves 32 to 73 codes without one, and leaves the rest to /DW 1000.
So only such Type0 fonts are decoded. Type 3 fonts and simple fonts, whose widths run
from /FirstChar to /LastChar, are not; none of the 16 is either.

That leaves one gap in the rule: a producer that numbers glyphs in order of use and also
leaves glyphs of the default width out of /W. A page drawing one of those glyphs fails the
width test. Only a page that draws none of them, while one of them is numbered between
the codes it does draw, could pass. The tests on built fonts exercise these rules. That a
gap in /W means an original glyph order is argued from how the two numberings assign
codes, and checked on the 16 real fonts; it is not proved.

Decoding runs after #868's `_with_layer_marks` has put the marks the spans lack into
them, against the text output as printed (#868 `cd0f19c59`). Decoded first, a font whose
codes print as combining marks would leave spans lacking marks the text output holds; the
marks could not be placed, and the page would fall back to its undecoded text-output lines
(review round 2). In this order, under PyMuPDF 1.26, such a font is decoded and its lines
kept. PyMuPDF 1.28 gives a combining mark the origin of the character before it, and can
carry a line's leading marks onto the line above. There the built lines are not the lines
drawn, and nothing is decoded. On a page where
a mark has been put into a span, the spans no longer match the `rawdict` read and nothing
is decoded. Under PyMuPDF 1.26.7 that leaves the page level below unchanged.

The other thresholds sit between what chance gives on this sweep and the weakest real
evidence. The page-level run scores every shift but the one found against the lines OCR
reads. It does so for every font with unmapped characters, with the font rules switched
off: 79 font-pages on 58 pages, 20 of them with some shift reading a line. (Review round
3: the first measurement saw only the fonts those rules leave.)
- **The fonts the rules leave:** the most decoded letters or digits in one line OCR reads
  under a wrong shift is 2 (OR-19-0002, +30: "11"). So no wrong shift has an evidence line
  at all.
- **All fonts:** the most is 23, AL-20-0004's ArialMT at +29. That is the Arial family's
  shift, reading the font's own typed "4/6/2020" and "Flexibilities; among other", which
  the rules refuse because three objects carry the name. Without it, the most is 2 again
  (`evidence/summary.json`, `chance_all_fonts_*`).

Here "wrong" excludes, for a font no shift
was found for, the shift found for a font of the same name elsewhere in the sweep:
MO-22-0012's one Minion Pro line, "6/6/2022", is read at +31, the shift of every other
Minion Pro, with 6 digits. Every right detection has evidence from at least two classes.
The weakest is exactly at the threshold: WA-14-0003's two lines "10 P & I" and
"12 P & I", 4 each, five distinct glyphs.

## Invariants

Property tests (Hypothesis) in `tests/test_ocr_shifted_font_layers.py`, with example tests
on built PDFs and on 11 retained pages; they pass under PyMuPDF 1.26.7 and 1.28.2. The
retained pages run under every text option; the built pages under the default one. The
built PDFs use Type0 Identity-H fonts, not
embedded, whose codes are 0xE000 above ASCII: MuPDF reads a code below about 0x1000 of
such a font through its substitute font's glyph order (code + 29) but has no Unicode for a
higher one and prints the code, as it does for the shifted fonts' embedded programs. A
font's /W and a ToUnicode map for some of its codes can be chosen; Type 3 fonts, whose
codes above U+007F have no Unicode, are built for the Type 3 cases. Two such fonts can
share a name, and a mapped font or an annotation's font can share a name with them.

- S1-S3, decoding a line: one character for one; a mapped character, or one of a font
  with no shift, is unchanged; a shifted character becomes chr(code + k) in printable
  ASCII, and the line is undecodable exactly when one would leave it; no shifts is the
  identity.
- S4, learning shifts: equal to a brute-force reference that tries every shift from -768
  to 255 on every single-font line, reads it with #868's brute-force reader, and applies
  the thresholds as numbers rather than the module's constants (a differential test).
- S5, round trip: ASCII lines written by a shift k and read by OCR give k back when the
  evidence is enough and no other shift has any, and decode to the lines exactly; with
  too little evidence, no shift.
- S6: line order, repeated lines and lines without unmapped characters change nothing;
  shift 0 is never applied. A line that decodes under a font's shift to a line's text with
  fewer decoded characters adds nothing to that shift's evidence: the font keeps its shift
  unless the line is evidence for another shift (then it has none), and no other font
  changes. (Review round 2: the test computed its baseline after adding such lines, so it
  did not test the claim, which as first written, "change nothing", was too strong.)
- S7-S8, on the retained pages under every text option and on the built pages: the `rawdict` spans are
  the `dict` spans (decoding is not skipped); paint and font never change; a span without
  an unmapped character is unchanged; a page without one is unchanged; a font whose
  characters in a line are partly mapped is not decoded there.
  - A font name shared by two font objects is not decoded. The pairs tested: two
    unmapped; unmapped and mapped; a page's and an annotation's; a Type0 font named by
    its descendant; two names MuPDF cuts alike, a Type 3 font's among them, its /Name
    direct or indirect; one in a soft-mask group, written as a dictionary or as a stream;
    one a graphics state selects, its /Type indirect; one in an annotation of an unknown
    subtype. A long Type 3 name does not shadow a font named as it reads uncut.
  - A line is decoded whole or not at all, including when one of its spans would decode
    outside printable ASCII or keep a control character.
- S9: the unmapped characters are exactly those PyMuPDF's text trace, another device,
  reports as U+FFFD, origin for origin, on all 29 retained pages of the two fixtures (a
  differential test). Every span holding one carries MuPDF's UNICODE_IS_CID or
  UNICODE_IS_GID mark (233 wholly unmapped spans among them). The converse fails: on
  WV-23-0001 page 132, nine marked spans hold characters MuPDF maps, so the mark alone does
  not say which characters to decode. And a character pairs with the other read's only
  where the reads agree at its origin.
- S10: only a Type0 font is decoded, and only when its /W gives a width for every code it
  draws unmapped on the page and leaves a code without one between the least and
  greatest of those.
  - Not decoded: a Type 3 font, named or not, and a font numbering its glyphs in order of
    use (the review's "89:;<=>?@AB"), however its /W is written: dense, with .notdef at
    0, or with a width far above. Nor is a font whose /W misses a code it draws.
  - Decoded: a font only an annotation's appearance draws.
  - /W read back gives exactly the codes written, as merged ranges (a property test).
  - A font whose codes print as combining marks is decoded, and the page keeps its lines,
    under PyMuPDF 1.26, since decoding follows `_with_layer_marks`. Under 1.28 nothing is
    decoded there.
- S11: when the page's fonts can't be known for certain, nothing on the page is decoded,
  and nothing raises. The cases tested: a font written inline in an appearance; a
  /BaseFont or /Subtype written as a reference (MuPDF resolves the name); an inline
  annotation; an inline descendant; an appearance referred to with generation 1, or to
  an object the file lacks; an unused font resource that does; a page tree too deep to
  follow; a walk that reaches its limit, counting an object met twice once.

#868's real-page tests now merge the decoded spans. Its invariant "every painted span
without a control character is in the page text" holds for lines decoding leaves alone;
decoded lines are checked whole instead.

Mutation check (`mutate_shifts.py`): broken variants of the decoding, run against the three
OCR test files. Before review round 1 the tests killed 18 of 19, and after it 26 of 27.
After review round 2, 36 variants, run at `e4bb92509`, before merging #868's
`a14678efb`, which changes none of the code they break: 35 killed. Nine are new, and each
undoes a round-2 fix:
- an annotation font's indirect names read bare;
- references of another generation followed;
- the annotation walk stopping silently at its limit;
- no /W rule;
- a /W without a gap allowed;
- codes missing from /W allowed;
- decoding before the marks are placed;
- an unnamed Type 3 font counted under one name;
- /W ranges beyond a two-byte CID read.

The test written for each kills it. That run left out #868's
`test_a_number_is_read_only_as_a_whole_token`, which failed then for a reason of #868's own
(fixed in `7639a8db2`), and run 6 was stopped when #868 moved.

After review round 3, 43 variants at `d4f4b9c12`: 42 killed. Seven are new, and each
undoes a round-3 fix:
- a Type0 font named by its own /BaseFont;
- names not cut to 31 bytes;
- soft-mask groups and graphics-state fonts not walked;
- tiling patterns not walked;
- the page's /Annots not walked;
- walk errors raised;
- a line that keeps a control character decoded.

Seven older ones were rewritten for the new code (S11, S23, S24, S28, S30 to S33). Among
them, S32 puts back round 2's /W rule (a gap anywhere), and a test now kills it. The one
left, S12, reads the first status at an origin instead of the k-th. It is equivalent: a
status is used only where every character at its origin has the same one.

After review round 4, 49 variants at `e28f15f0c`: 48 killed, S12 again the one left. Six
are new, and each undoes a round-4 fix:
- a Type 3 font also named by its uncut name;
- a stream that a graphics state reaches not followed further;
- an indirect /Type not resolved;
- a page tree too deep taken as having no resources;
- any single reference taken as the descendant;
- the limit checked before a holder already walked is skipped.

S30, S35 and S37 were rewritten for the new code. Logs: `evidence/mutation-r1.txt` to
`mutation-r9.txt`.

## Before and after: every page the overlay rule reaches

Both sides were run on the same 1,041 pages in 328 retained PDFs, with Tesseract 5.5.3
cached by rendered page image: 3,123 hits for the two sides, 4,164 from round 3 on with
the all-fonts chance pass, 0 misses in every run. These figures hold for the rule after
review rounds 1 to 4. The rule before round 1 (no font-object or class test, lines decoded in part)
also found AL-20-0004's ArialMT; it gave the same lines and one more, the clipped "Acting
Deputy D". The before side is this branch with
`_pdf_decoded_span_lines` returning its spans, which is #868's code at `8a2452fea`. The
measurement first ran on #868 at `c64009789`, before it counted Type 3 spans as painted,
and gives the same lines, pages and documents; the page level, re-run on #868 at
`c4ccca4ee`, at `97e3e935e` (Type 3 font names read as MuPDF 1.26 does) and at `55bba979b`
(mapped spans of garbled fonts kept, layer marks), gives the same lines again. #868's later
code, to `c70a950a2`, changes docstrings and, in `_pdf_inline_font_key`, removes and then
restores one check. That function is called only for an inline Type 3 font, and the 328
PDFs have none: their 36,137 font entries, 600 of them Type 3, are all indirect objects.
So no figure here moves. After review round 2's fixes (`a77efdd49`), with #868 merged at
`cd0f19c59` (decoding after `_with_layer_marks`, `dfe3833be`) and at `a14678efb`
(`a5bc14776`), the page level gives the same lines on every page again
(`evidence/r7-review-r2-fixes/`, `r8-dfe3833be/`, `r9-a5bc14776/`), and so does it after
review round 3's (`d4f4b9c12`, `r10-d4f4b9c12/`) and round 4's (`ab9a4b6d3`,
`r11-ab9a4b6d3/`).

| | |
| --- | ---: |
| Pages with an unmapped character | 58 |
| Pages with a detected shift | 16 (Minion Pro +31 on 13, Times New Roman +29 on 2, Arial +29 on 1) |
| Pages whose text changes | 8 (8 PDFs) |
| Lines added | 20 (61 words) |
| typed values: dates, notes, a page count | 16 (50 words) |
| typed names and titles | 3 (9 words) |
| a clipped copy of a typed title OCR read whole | 1 (2 words) |
| Lines removed (all garbled) | 3 (4 words) |
| Errors | 0 |

- The typed values recovered: "09/30/20" (MA-20-0024); "11/30/15", "12/10/15", "12/01/15"
  (OR-15-0006); "4, 13, 25, and 32", the two P&I notes, "5/2/19", "11/7/19", "11/1/19" and
  "David L. Meacham" (OR-19-0002); the P&I note "9/24/15: The state authorizes P&I changes
  to box 8 and box 9.", "1/01/14", "9/28/15", "David L. Meacham" and "Associate Regional
  Administrator" (WA-14-0003); "4/1/19", where OCR read "4 /1/19" (WA-19-0012); "1/1/2020"
  (WA-20-0004). MO-22-0012 page 3 adds "4*", the page count with the footnote marker for
  its pen-and-ink note.
- The noise added is a clipped rendering of WA-19-0012's title, "Deputy D", beside the
  whole "Acting Deputy Director" that OCR read. The removed lines are "1(:", "%JSFDUPS"
  and "%FQVUZ %" (the last is now "Deputy D").
- On 8 more pages a shift is found and every decoded line is one OCR read, so the text is
  unchanged. Examples: AR-21-0003, MD-19-0003, NV-19-0013, OH-20-0005, SD-21-0002.
- Not decoded:
  - AL-20-0004's ArialMT: three font objects carry the name, one of them mapped (the
    signature). Nor are the lines that mix ArialMT with Arial; OCR read them.
  - WA-19-0012's second clipped copy of the title, "Acting Deputy D". It is drawn where
    another line's character is, and the two reads draw a different number of characters
    there.
  - CA-25-0037's 15 pages, and pages of CT-24-0003, CT-24-0006, IL-21-0006, MI-25-0101,
    MI-25-1501, NC-24-0033 and WI-22-0009. Their Type 3 "T" fonts number their glyphs from
    \x00 in the order the page first uses them (CA-25-0037 page 16 begins
    "\x00\x01\x02\x03"), so no constant shift reads them, and their lines mix mapped and
    unmapped characters.
  - Identity-H fonts with a few unmapped characters inside otherwise mapped lines:
    MD-25-0012 (whose OpenSans name two objects carry), MI-25-0015, MI-26-0001 and
    WV-23-0001.
  - NV-20-0002 page 3, whose Minion Pro name two objects carry and whose line mixes them
    (OCR read it).
  - Fonts with too little evidence. MO-22-0012's Minion Pro has one line, "6/6/2022", 6
    digits of one class, which OCR read. OR-15-0006 page 4 and OR-15-0007 page 4 have one
    typed date each and no line OCR read. Evidence is per page, so OR-15-0006 page 3's +29
    does not carry over, and "12/10/15" on page 4 is still lost.
- An earlier estimate, in the task that started this work, applied a shift found on a page
  to all of that page's control-character lines, and came to 1,110 lines OCR did not read
  on 17 pages, some of them noise on CA-25-0037. Per font, and only for unmapped
  characters, the lines that change are the 23 above.

Document level: `_extract_blocks` on the 327 manifest documents behind the PDFs, with and
without decoding and the same OCR cache, gives no error on either side. 8 documents
change, one block each, and no block count, heading or section label changes. The words
added and removed are the page lines above, 61 added and 4 removed. Re-run on #868 at
`55bba979b`, after review round 2's fixes, at `dfe3833be` and `a5bc14776`, and after
review rounds 3 and 4, it gives the same documents, blocks and words.

## Scopes whose pages change; #864

5 scopes (`docs/ingest-runs/2026-10-13-ocr-overlay-shifted-font-layers-scopes.csv`), the
Medicaid state plans of AL, MA, MO, OR and WA (`us-xx/policy/2026-09-13-medicaid-state-plan`).
All five are among #868's 52. #864's successors of them (`<scope>-r2026-10-13-hollow-roots`)
must be built with this rule as well as #868's: in place while #864 is unmerged, or as a
further successor revision after it merges. At #864's head `8669292f6` all five
successors are built and signed.

## Reproduce

Scripts and outputs: `~/reviews/axiom-corpus-shifted-font-layers-2026-10-13/` (README). Run
from the worktree with its `.venv/bin/python` (GIL Python 3.14):
`scripts/page_before_after.py` (the table), `scripts/summarize.py` (families, chance),
`scripts/doc_before_after.py` with `DECODE=0` and `DECODE=1`, and `scripts/doc_diff.py`
(document level), `scripts/build_fixture.py` (the test fixture), `scripts/mutate_shifts.py`,
and the probes `scripts/font_identity_probe.py`, `scripts/width_probe.py`,
`scripts/font_program_probe.py` and `scripts/inline_font_lookup_probe.py`.
