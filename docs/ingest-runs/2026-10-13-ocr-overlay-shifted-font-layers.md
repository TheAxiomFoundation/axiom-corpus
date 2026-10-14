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
`_pdf_decoded_span_lines` runs before `_without_garbled_spans`:

1. **Unmapped characters** (`_pdf_unmapped_characters`): those printed as U+FFFD by a
   second `rawdict` read without TEXT_CID_FOR_UNKNOWN_UNICODE, matched by origin and order
   at that origin, and not U+FFFD in the first read. The characters come from the
   `rawdict` read with the page's flags and sort, whose spans must be the `dict` spans
   exactly; otherwise nothing is decoded.
2. **A font's characters in a line** are candidates only when none of that font's other
   characters in the line is mapped. MuPDF's own spaces (U+0020) are the exception.
3. **A shift k** reads code c as chr(c + k), and only into printable ASCII, U+0020 to
   U+007E (`_pdf_decoded_layer_line`).
4. **Evidence** for font f and shift k (`_pdf_font_code_shifts`): a line whose candidate
   characters are all f's, decoded by k, that the OCR text reads (#868's
   `_ocr_read_line`), with at least 4 letters or digits among the decoded characters.
   Font f's shift is k when no other shift has evidence for f and k's distinct evidence
   lines hold at least 8 decoded letters or digits. Shift 0 (codes that are the text)
   counts as a rival but is never applied.
5. **Decoding.** Each span's candidate characters of a font with a shift are decoded, one
   character for one. A span its font's shift cannot decode becomes a space. Every other
   character, and every span's paint and font, is unchanged. The decoded spans no longer
   hold control characters, so `_without_garbled_spans` keeps them, and #868's merge
   appends the lines OCR did not read.

The thresholds sit between what chance gives on this sweep and the weakest real evidence.
Across every font with
unmapped characters on the 1,041 pages, under every shift but the font's own, the most
decoded letters or digits in one line OCR reads is 2 (OR-19-0002, +30: "11"). So no wrong
shift has an evidence line at all. The weakest right detection is exactly at the
threshold: WA-14-0003's two lines "10 P & I" and "12 P & I", 4 each.

## Invariants

Property tests (Hypothesis) in `tests/test_ocr_shifted_font_layers.py`, with example tests
on built PDFs (Type 3 fonts whose codes are above U+007F, so MuPDF has no Unicode for any
of them, beside a mapped font of the same name) and on 11 retained pages:

- S1-S3, decoding a line: one character for one; a mapped character, or one of a font
  with no shift, is unchanged; a shifted character becomes chr(code + k) in printable
  ASCII, and the line is undecodable exactly when one would leave it; no shifts is the
  identity.
- S4, learning shifts: equal to a brute-force reference that tries every shift from -768
  to 255 on every single-font line and reads it with #868's brute-force reader (a
  differential test).
- S5, round trip: ASCII lines written by a shift k and read by OCR give k back, unless
  another shift also has evidence, and decode to the lines exactly; under 8 letters or
  digits of evidence, no shift.
- S6: lines without unmapped characters, line order and repeated lines change nothing;
  shift 0 is never applied.
- S7-S8, on every built and retained page under every text option: the `rawdict` spans are
  the `dict` spans (decoding is not skipped); paint and font never change; a span without
  an unmapped character is unchanged; a page without one is unchanged.

#868's real-page tests now merge the decoded spans. Its invariant "every painted span
without a control character is in the page text" holds for lines decoding leaves alone.
Decoded lines are checked whole instead, because a decoded value can arrive as fragments
of one line: AL-20-0004's "0", "3", "/01/2020" in three fonts. A mutation check (19 broken
variants of the decoding, `mutate_shifts.py`): round 1 killed 14 of 19; tests were added for the four survivors that a test could catch (a 3-letter evidence line, decoding into U+007F, an undecodable span kept raw, mapped letters counted as evidence), and round 2 kills 18 of 19. The one left, S13, counts a character printed as U+FFFD in both reads as unmapped. It is equivalent in practice: MuPDF prints a code under the flag even for a glyph named uniFFFD (checked on a built Type 3 font), so U+FFFD with the flag needs a character whose code is 0xFFFD.

## Before and after: every page the overlay rule reaches

Both sides were run on the same 1,041 pages in 328 retained PDFs, with Tesseract 5.5.3
cached by rendered page image (3,123 hits, 0 misses). The before side is this branch with
`_pdf_decoded_span_lines` returning its spans, which is #868's code at `8a2452fea`. The
measurement first ran on #868 at `c64009789`, before it counted Type 3 spans as painted,
and gives the same lines, pages and documents; the page level, re-run on #868 at
`c4ccca4ee` and at `97e3e935e` (Type 3 font names read as MuPDF 1.26 does), gives the same
lines again.

| | |
| --- | ---: |
| Pages with an unmapped character | 58 |
| Pages with a detected shift | 16 (Minion Pro +31 on 13, Times New Roman +29 on 2, Arial and ArialMT +29 on 1) |
| Pages whose text changes | 8 (8 PDFs) |
| Lines added | 21 (64 words) |
| typed values: dates, notes, a page count | 16 (50 words) |
| typed names and titles | 3 (9 words) |
| clipped copies of a typed title OCR read whole | 2 (5 words) |
| Lines removed (all garbled) | 3 (4 words) |
| Errors | 0 |

- The typed values recovered: "09/30/20" (MA-20-0024); "11/30/15", "12/10/15", "12/01/15"
  (OR-15-0006); "4, 13, 25, and 32", the two P&I notes, "5/2/19", "11/7/19", "11/1/19" and
  "David L. Meacham" (OR-19-0002); the P&I note "9/24/15: The state authorizes P&I changes
  to box 8 and box 9.", "1/01/14", "9/28/15", "David L. Meacham" and "Associate Regional
  Administrator" (WA-14-0003); "4/1/19", where OCR read "4 /1/19" (WA-19-0012); "1/1/2020"
  (WA-20-0004). MO-22-0012 page 3 adds "4*", the page count with the footnote marker for
  its pen-and-ink note.
- The noise added is two clipped renderings of WA-19-0012's title, "Acting Deputy D" and
  "Deputy D", beside the whole "Acting Deputy Director" that OCR read. The removed lines
  are "1(:", "%JSFDUPS" and "%FQVUZ %" (the last is now "Deputy D").
- On 8 more pages a shift is found and every decoded line is one OCR read, so the text is
  unchanged. Examples: AR-21-0003, MD-19-0003, NV-19-0013, OH-20-0005, SD-21-0002.
- Not decoded:
  - CA-25-0037's 15 pages, and pages of CT-24-0003, CT-24-0006, IL-21-0006, MI-25-0101,
    MI-25-1501, NC-24-0033 and WI-22-0009. Their Type 3 "T" fonts number their glyphs from
    \x00 in the order the page first uses them (CA-25-0037 page 16 begins
    "\x00\x01\x02\x03"), so no constant shift reads them, and their lines mix mapped and
    unmapped characters.
  - Identity-H fonts with a few unmapped characters inside otherwise mapped lines:
    MD-25-0012, MI-25-0015, MI-26-0001 and WV-23-0001.
  - NV-20-0002 page 3, whose line mixes Minion Pro fonts (OCR read it).
  - Fonts with too little evidence. MO-22-0012's Minion Pro has one line, "6/6/2022", 6
    digits, which OCR read. OR-15-0006 page 4 and OR-15-0007 page 4 have one typed date
    each and no line OCR read. Evidence is per page, so OR-15-0006 page 3's +29 does not
    carry over, and "12/10/15" on page 4 is still lost.
- The brief's estimate, 1,110 recoverable lines on 17 pages, included CA-25-0037's Type 3
  fonts, which no shift reads. Per font, and only for unmapped characters, the lines that
  change are the 24 above.

Document level: `_extract_blocks` on the 327 manifest documents behind the PDFs, with and
without decoding, gives no error on either side. 8 documents change, one block each, and
no block count, heading or section label changes. The words added and removed are the
page lines above, 64 added and 4 removed. The OCR cache held 7,874 pages before and after
both runs, so no page was read by Tesseract anew.

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
(document level), `scripts/build_fixture.py` (the test fixture) and `scripts/mutate_shifts.py`.
