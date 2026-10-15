# OCR overlay: typed text-layer lines (2026-10-13)

PR #854 (merged `f98fa2bbd`) made `ocr: true` read a scanned PDF page by Tesseract when
its text layer is only an overlay: fewer than 30 words with a letter, over page images of
at least 100 dpi covering 90% of the page. `documents.py::_with_unread_layer_lines` then
appended a text-layer line after the OCR text only when one of its tokens with a digit
was missing from the OCR text's tokens anywhere on the page. That lost typed text. This
change replaces the merge rule and measures it on every page the overlay rule reaches.

Nothing was published, loaded or activated, and no merged scope was edited.

## The defect

Reproduced from retained bytes at `origin/main` `c3a8e1d0c`:

- A typed date is dropped when its day and year occur in another date.
  `us-hi/policy/cms/medicaid-state-plan/spa/hi-14-005/approval-document/page-3`, a
  CMS-179: OCR read "March 19, 2014" and nothing of the regional-office box, so the typed
  DATE APPROVED "November 19, 2014" was dropped, with the signer's name "Hye Sun Lee" and
  title.
- A typed word OCR misread is not restored.
  `us-nh/.../spa/nh-18-0001/approval-document/page-3` reads "18. DATE APPROVED: 531 30,
  2018"; the layer has "April 30, 2018".
- A line with no digit is never kept, so the typed name and title of the CMS signing
  official vanish: AK-13-0027-MM1, NE-12-07, IN-12-014, IN-15-008, MN-18-0002,
  NY-17-0014, NY-17-0069, NY-19-0046, OH-13-014 and OH-15-001.

## The rule

On a page `ocr: true` reads by OCR although it has a text layer (`_pdf_page_text`), the
layer is read from the `dict` output (`_pdf_layer_lines`): each line as its spans' text,
paint, font name and Unicode provenance, unsplit. A span is painted when its characters
are filled or stroked (PyMuPDF `char_flags`) with non-zero opacity. Its provenance
(`_pdf_span_mapped`) is "mapped" when PyMuPDF reports its characters (a fill or stroke
flag) and neither of MuPDF's flags for a glyph without Unicode (`FZ_STEXT_UNICODE_IS_CID`,
`FZ_STEXT_UNICODE_IS_GID`) is set, "unmapped" when one of those is, and unknown otherwise.
PyMuPDF starts a new span wherever these flags change (`extra.i`, `JM_make_spanlist`, in
1.26.7 and 1.28.2), so they hold for every character of a span. "Mapped" is exact;
"unmapped" can over-report: MuPDF sets the flag at the first glyph without Unicode and
keeps it for the rest of the same text-showing operation (`do_extract` in
`source/fitz/stext-device.c`, 1.26.12). Checked on the overlay pages under 1.26.7 against a
read without CID substitution, where a glyph without Unicode is U+FFFD (characters matched
by origin): none of 103,016 unflagged characters lacks Unicode, and 748 of 8,633 flagged
ones have it (`scripts/cid_flag_probe.py`). The #870 session found the same on
WV-23-0001 page 132.

PyMuPDF 1.26, which this repository locks, reports filled Type3 glyphs as neither filled
nor stroked, as it does invisible text, so under PyMuPDF before 1.27 a span in a Type3
font counts as painted. Type3 spans are found by the name MuPDF gives them: the font's
/Name (an indirect one resolved, its #xx escapes undone; a font written inline read
through the resources that hold it), its bytes read as Latin-1, less a six-character
subset prefix, or, without a name, "Unnamed-T3" (1.26) or "Type3 (<object> 0 R)" (1.28).
They are looked for in the page's resources and forms (PyMuPDF `get_fonts`) and in the
appearance streams of its annotations and widgets and the forms those draw, whose text is
extracted too but whose fonts `get_fonts` does not list (`_pdf_appearance_type3_font_names`;
on the overlay pages, 334 of which list annotations or widgets in /Annots, those streams
hold 112 TrueType and 226 Type1 fonts and no Type3 one, `scripts/annot_type3_scan.py`).
Anything in that scan that can't be read, such as a reference to a missing object, is
skipped: it only finds fonts and never fails a page.
An inline font whose resource name has a "/" (a lookup path would split at it and could
reach another font's dictionary) or a byte that isn't UTF-8 is named by the name PyMuPDF
lists for it, its /BaseFont ahead of its /Name; a Type3 font has no /BaseFont in a
conforming file, but one that does is missed (pinned in a test). From 1.27 the span's
paint is trusted: 1.27.2.3 and 1.28.2, the releases checked, report Type3 paint, and
every Type3 span on the overlay pages measured is filled under 1.28.2. The limit of the
lock: there, an invisible Type3 layer, or invisible text in another font sharing a Type3
font's name, counts as painted. On every version a Type3 span's provenance is unknown: its
glyph names are its map, and a shifted Type3 font's names are wrong (IL-21-0006's
"OPQRPST" carries neither flag under 1.28.2).

If the spans do not hold the text output's characters (whitespace, control characters and
combining marks aside; `sort_text` changes only the lines the text output prints), the
text output's lines, split at newlines only, are used instead, all counted as painted, so
no line without a control character can go missing. Combining marks the text output holds and the spans lack
are put into the spans before anything else (`_with_layer_marks`). Without `sort_text` the
text output is the dict lines joined by newlines, so each text-output line is lined up
with its dict line, and a missing mark goes into the span of the character before it,
taking that character's line, span, paint and font. A line whose spans' characters are not
its text-output line's with only marks taken out is left as it is when that text-output
line holds a control character, or when its spans do and the text-output line has no mark
they lack; otherwise, or when the line counts differ, the text output's lines are used.
That keeps the accent of a garbled line whose control "spaces" `sort_text` drops from the
text output ("Name: José"). Limit: a line left as it is keeps its spans in other fonts
without a mark its text-output line holds (on the text output's lines the whole line would
go); that takes a text-output line with a control character and a lacking mark, which
`sort_text` leaves only for controls above U+0020. Under 1.26.7 neither happens on any overlay page, with or
without `sort_text`. Under 1.28.2, WV-23-0001 pages 132, 237 and 358 lack Khmer marks in
their spans that their text output prints: they are put back, and with `sort_text`, which
rebuilds those lines, the text output's lines are used. Those three pages then skip the
garbled-font rule's span-level judgement (a line with a control character still goes
whole) and the recognition filter (every line counts as painted); their text is the
visible OCR of screenshots, junk either way.

1. **Garbled fonts** (`_without_garbled_spans`). A span holding a control character other
   than tab, newline, carriage return, VT or FF is a garbled font's, and so is every other
   span on its line in a font of the same name: such a font gives the line's codes wrong
   characters, some of them control characters (CA-25-0037's "5678", "9C<:"). Those spans
   are left out whole, before anything splits them (Python's `splitlines()` breaks lines
   at U+001C to U+001E and U+0085, and `split()` strips U+001F, so judged after splitting
   a shifted font's "2EQI\x1e" would pass as "2EQI"). The exception is a mapped span when
   every control-character span of its font on the line is unmapped: the garbage is the
   codes the font's Unicode map leaves out, and the mapped span's characters are the
   ones the font's own map gives. On
   NV-20-0002 page 3, "March 13, 2020" is set in a MinionPro subset whose map gives, on
   that line, only the "3"; ".BSDI\x01\x12" and "\r\x01\x13\x11\x13\x11" are "March 1"
   and ", 2020" given as CIDs, 31 codes below the characters. The runs of kept spans between left-out ones are joined by one
   space. Spans in other fonts on the line, such as a date typed beside a garbled label,
   are kept. A line is painted when one of its kept spans with visible characters is. The
   rule leaves out 490 control-free spans on the overlay pages under 1.26.7 (213 distinct
   texts, all symbol and digit strings such as "$#", ":;<=", "5MN1"; 35 under 1.28.2,
   which builds fewer spans) and keeps 19 by provenance on both versions: NV-20-0002's "3"
   and 18 punctuation shards of WV-23-0001's screenshot text. All 490 are in Type3 fonts
   (`scripts/dropped_span_unicode.py`). Its limits: a clean span in the same font as a
   garbled span on its line is still left out when its provenance is unknown (a Type3
   font, invisible text under PyMuPDF 1.26), when it is flagged as lacking Unicode only
   because a glyph before it in the same text-showing operation lacked it, or when the
   font's map itself gave the control character (a map that does so after such a glyph
   is not caught, and its other spans are kept). And "mapped" means the font's own map gave
   the characters, not that they are right: a non-Type3 font whose map gives wrong
   characters for some codes and none for others keeps its mapped garbage (pinned in a
   test). On the overlay pages that is the 18 WV-23-0001 shards, so 1 of the 19 spans kept
   by provenance is typed text.
2. **Recognition layers** (`_without_failed_recognition_lines`). Painted lines are all
   kept. An invisible line (text render mode 3, or fully transparent) belongs to a
   recognition layer, an earlier OCR of the same image, not typed text. Two kinds are
   dropped: a fragment, fewer than three letters (`str.isalpha`, counted before
   lower-casing, after NFKC) and no digit ("cc:", a stray "L"); and every invisible line of a failed layer, one
   with at least five distinct words of three or more letters of which fewer than a third
   occur in the OCR text (as one of its words, or, for words of six or more letters,
   inside its letters run together, since recognition layers run words together). Letters
   are counted before lower-casing, which can lengthen a word (İ becomes two code points).
3. **The merge** (`_with_unread_layer_lines`). A remaining line is appended after the OCR
   text unless the OCR text already holds the whole line: the same characters in the same
   order, starting and ending at token boundaries (a line may skip punctuation that leads
   or trails an OCR token, never a currency sign, minus or percent sign). Spacing next to a
   letter is not compared, because layers and OCR break words differently
   ("EffectiveDate", "of39"); spacing between digits and punctuation is ("1 2" is not
   "12"). Quote and dash variants compare equal. Lines with a control character or without
   a letter or digit are never appended, as before.

A line counts as read wherever on the page the OCR text holds it: a short typed value
equal to text OCR read in another field (a date typed in two boxes) is not appended
again. The text is on the page; which field it belongs to is not recorded.

### Invariants

Stated and tested in `tests/test_ocr_layer_line_properties.py` (Hypothesis, against
written-out references that do not share the implementation's code):

- S1 to S3 for garbled fonts: a span with a control character other than ordinary
  whitespace is left out, with every other span on its line in the same font except a
  mapped one when all the font's control-character spans there are unmapped; the line is
  the non-empty runs of kept spans between them, in order, joined by one space; no line
  returned holds such a control character; a line is painted exactly when one of its kept
  spans with visible characters is.
- K1 to K3 for combining marks: with no mark missing the spans come back unchanged;
  otherwise only marks are added (each span's other characters, paint, font and
  provenance kept), each line whose spans are its text-output line less some marks
  becomes that line exactly, with each added mark in the span of the character before
  it, a line that does not line up comes back as it was, and every mark of a text-output
  line without a control character is in its line; it gives up (and the text output's
  lines are used) exactly when the lines do not line up and the exception does not
  apply (another count, or a line whose spans are not its text-output line less some
  marks, unless that text-output line holds a control character, or its spans do and it
  lacks no mark), checked against a search written independently of the single pass it
  uses.
- R1 to R5 for recognition layers: the result is a subsequence of the input; every
  painted line is kept; an invisible line is dropped only as a fragment or in a failed
  layer; more OCR text never drops a kept line; applying it to its own result changes
  nothing.
- M1 to M8 for the merge: the OCR text is a prefix of the result, which is the OCR text
  exactly when nothing is appended; every layer line with a letter or digit and no
  control character is held by the result (brute force over every run of OCR tokens);
  nothing is appended when OCR read every line (lines cut from OCR's own tokens, respaced
  next to letters, trimmed of edge punctuation, quote and dash variants swapped); the
  appended lines are exactly the unread ones, once each, in layer order; merging twice
  changes nothing; with blank OCR the layer is returned unchanged; more OCR text never
  appends more; every line #854's rule appended is held unless an earlier step dropped
  it.
- Together: every painted line S1 keeps is in the page text wherever it has a letter or
  digit (on the text output's lines when those are used).

`tests/test_documents_ocr_overlay.py` builds PDFs with filled, stroked, render-mode-3 and
transparent text, a scanned page whose typed lines are set in a Type3 font written 25
ways (named, unnamed, subset-prefixed, #xx-escaped or indirect names; inline, inherited or
in a form, under resource names with a space, a "/" or a byte that isn't UTF-8) or drawn
by an annotation's appearance stream (the font referenced, inline, or in a form it
draws; under resource names with a "/" or a byte that isn't UTF-8; through a dictionary of
appearance states; from an annotation reference of generation 1), pages whose annotations
reference missing objects (seven ways, none of which may fail the page), and pages whose
text output holds a combining mark the spans lack. The 22 pages in
`tests/fixtures/ocr_overlay/` (19 named in the defect report or measured below,
AL-20-0004 page 4, whose shifted span splits at U+001E, NV-20-0002 page 3, whose mapped
"3" is kept beside unmapped codes, and WV-23-0001 page 132, whose marks PyMuPDF 1.28's
spans lack) are run through `_pdf_page_text` on the retained PDFs (checked by SHA-256) with
Tesseract's stored output, with and without `sort_text` and `ignore_actual_text`. A
mutation check runs 77 broken variants of the rule against these tests; its result is
recorded in the PR.

## Measurement

Every page the overlay rule reaches: the 1,041 page entries in 328 retained PDFs of
`ocr: true` manifest documents listed by #853's sweep (`ocr-rule-sweep-final.json`; 1,040
distinct pages, one Ghana page being listed under two manifests), all of them read from
retained bytes, with PyMuPDF 1.26.7 (the lock). CI installs 1.28.2, which splits some lines
into spans differently; it gives the same page text on 1,031 of the 1,040 pages, and the
other 9 differ only in junk lines of IL-21-0006, WI-22-0009 and WV-23-0001 (shifted-font
strings and screenshot noise, two of which a text-only test calls typed: WI-22-0009's
"./01/2353/637" and WV-23-0001's "1" among Khmer vowel signs). Tesseract 5.5.3 (eng) output, at each
manifest's `ocr_dpi` (the default 200, or 300 for the six Ghana documents), was cached by
the exact rendered page image, so both rules read the same OCR text. Five pages have blank
OCR text; both rules return their layer unchanged.

### Pages

| | #854 | This change |
| --- | ---: | ---: |
| Layer lines appended | 671 | 914 |
| Typed or legible lines appended (words) | 477 (1,654) | 674 (2,299) |
| Junk lines appended (words) | 194 (512) | 240 (596) |
| Pages with junk appended | 101 | 80 |
| Pages missing a legible layer word (words) | 20 (33) | 1 (1) |

366 pages in 160 PDFs append different lines. Of the 207 lines #854 appended that are no
longer appended, 138 are lines OCR read with other spacing or quote style (41 of them the
ND-20-0004 footer), 26 are shards of garbled-font spans split at separator control
characters (CA-25-0037 "9:;<=>", IL-21-0006 and WI-22-0009 "%@5"), and 43 are noise from
failed recognition layers (MT-13-0048-MM's mirrored layer, NJ CHIP 22-0031, NJ-19-0009,
UT-14-0007-MM, and the shifted signature dates on ID-20-0001 and MO-20-0016).

"Missing a legible layer word" is the loss measure used for #864: a letter-only word of
five or more letters of the page's layer (lines without control characters), in the
system word or name list, that the page text lacks in any form (with spacing and
punctuation removed, or as a near-identical word). The one remaining word, "tint's", sits
in a noise line of NJ CHIP 22-0031's failed recognition layer. The measure does not see
short lines. The recognition filter drops 20 invisible lines that a text-only test would
call legible or a value, none of which #854's rule appended unless it had a digit: "cc:"
three times (AK-13-0027-MM1, AK-13-0029-MM3, ID-14-0005, all read by OCR as "ce:"), a
checkbox "X" (IA-20-0003) and "x" (NJ CHIP 22-0031), "T. N. #" twice (UT-13-021),
"IfApplicable)" (ID-20-0001, read by OCR as "(/f Applicable):"), and 12 lines of failed
layers (MT-13-0048-MM, NJ CHIP 22-0031) such as "0", "4" and "time iti .state):".

"Junk" is a line that is not text a reader could use, by reviewed family: an invisible
recognition layer's misreadings and fragments (every line of a layer that fails against
the OCR text counts here, whatever its text, such as "0" and "4. 1.4. U"), recognition over sideways scans
(UT-14-0007-MM, UT-14-0004-MM), text in a font whose codes are shifted ("%JSFDUPS" for
"Director", and shards of garbled spans), and the visible OCR of screenshots in
WV-23-0001. Each family was reviewed on rendered pages.

Junk this change appends that #854 did not: 129 lines (293 words).

- 54 painted lines, which the rule keeps by design because nothing separates them from
  typed text: 48 in WV-23-0001 (a visible OCR layer over screenshots of an eligibility
  system) and 6 shifted-font lines with no control character on their line (MA-20-0024
  "%JSFDUPS", WA-19-0012 "%FQVUZ %", and IL-21-0006 and WI-22-0009 "OPQRPSTVTPWTX", set
  in Type3 fonts).
- 75 invisible lines: 43 from UT sideways scans on pages whose layer has fewer than five
  words (too few to judge) and 32 misreadings from layers that agree with OCR elsewhere
  (MD-19-0008, NJ CHIP 22-0031, a Uganda gazette page and others).

Junk #854 appended that this change does not: 83 lines (209 words): 26 garbled-font
shards; 38 misreadings, 24 of them dropped with their failed layers and 14 (30 words) now
read by OCR; and 19 sideways-scan lines from failed layers.

The two layers named in the defect report append nothing: UT-14-0007-MM page 21 ("ac al
ckm cl err", none of its words in the OCR text) and ID-20-0001 page 3 ("Ejhjubmmz", a
signature string written one code above ASCII in the same Helvetica as the form labels,
two of eight words in the OCR text). Of the 185 invisible layers with at least five words, 15
share none of their words with OCR and 3 more share under 10%; 6 share 20% to 50%; the
other 161 share 50% or more, 116 of them 90% or more. The cut-off sits in a flat range
(`scripts/final_checks.py`, final code): 0.15, 0.25, one third and one half gate 18, 19,
20 and 24 layers, holding 106, 109, 113 and 141 unread lines. One third gates one layer
more than 0.25, ID-20-0001 page 3; one half would add a Uganda gazette page (38%),
MD-19-0008 pages 14 and 5 (39%, 41%) and DC-16-0012 page 15 (48%), which hold legible
lines among their misreadings.

### Documents

Re-extracting the 327 manifest documents behind those PDFs with `_extract_blocks` under
#854's rule and this one, from the same OCR text: no error on either side; no block
count, heading or section label changes; 155 documents and 361 pages change (51,608 to
52,292 words on those pages). Every token of the old page text that the new one lacks,
even ignoring spacing, is a garbled-font shard or noise from a failed recognition layer,
except one en dash (IA-20-0003 page 3, where the layer line is now read by OCR's hyphen).

## Scopes whose pages change

52 scopes whose extracted documents change, listed with their changed documents and
pages in
[`2026-10-13-ocr-overlay-layer-lines-scopes.csv`](2026-10-13-ocr-overlay-layer-lines-scopes.csv):
the CMS Medicaid state plans of AK, AL, AR, CA, CO, CT, DC, GA, HI, IA, ID, IL, IN, KS,
LA, MA, MD, ME, MI, MN, MO, MT, NC, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, TN,
UT, VA, VT, WA, WI, WV and WY (`us-xx/policy/2026-09-13-medicaid-state-plan`); the CMS
CHIP state plans of CO, CT, ME, MT, NE, NJ, PA and SD
(`us-xx/policy/2026-09-13-chip-state-plan`); and
`us-hi/regulation/2026-09-10-medicaid-state-eligibility-manual`.

Pages of five more scopes append different lines without changing their extracted
documents, because each changed page lies outside its manifest's `page_windows`:
`gh/statute/2026-07-07-gh-appropriation-act-2025`,
`gh/statute/2026-07-07-gh-vat-reform-2026-anchors`,
`ug/regulation/2026-07-08-ug-vat-rate-order`, `ug/statute/2026-07-08-ug-appropriation-2022`
and `ug/statute/2026-07-08-ug-excise-2024-rows`.

PR #864 builds successor scopes (`<original>-r2026-10-13-hollow-roots`) for 51 of them
with #854's rule. Those successors must be rebuilt with this rule: in place while #864 is
unmerged, or as a further successor revision after it merges. The Hawaii eligibility
manual scope has no successor in #864.

## Follow-ups

- **Shifted-font layers** (draft PR #870, stacked on this one). On 24 pages a constant
  code shift (28 to 31) turns some control-character lines into text OCR read, so the
  font is offset from ASCII. Applied to the same pages' other control-character lines, it
  gives 1,110 lines OCR did not read, on 17 pages: some typed values (OR-15-0006
  "11/30/15", "12/10/15"; MA-20-0024 "09/30/20"), some still noise (CA-25-0037). Both
  rules drop them as control-character lines. Decoding such fonts would recover the typed
  values and the shifted lines above; #870 measures 21 lines added on 8 pages, 19 of them
  typed values or names.
- **Sideways scans.** On UT-14-0007-MM's sideways slides Tesseract's own text is noise
  ("(uas)pjiy usoqun sjuerddy" for "Applicant's Unborn Child(ren)"). Orientation
  detection before OCR would read them.
