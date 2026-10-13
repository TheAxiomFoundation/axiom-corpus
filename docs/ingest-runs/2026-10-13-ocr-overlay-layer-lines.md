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

On a page `ocr: true` reads by OCR although it has a text layer (`_pdf_page_text`):

1. **Recognition layers** (`_without_failed_recognition_lines`). PyMuPDF reports, per text
   span, whether its characters are filled or stroked (`char_flags`) and its opacity. A
   line is painted when any of its spans with visible characters is filled or stroked
   with non-zero opacity. An invisible line (text render mode 3, or fully transparent)
   belongs to a recognition layer, an earlier OCR of the same image, not typed text.
   Painted lines are all kept. Two kinds of invisible line are dropped:
   - a fragment: fewer than three letters and no digit ("cc:", a stray "L");
   - every invisible line of a failed layer: one with at least five distinct words of
     three or more letters, fewer than a third of which occur in the OCR text (as one of
     its words, or, for words of six or more letters, inside its letters run together,
     since recognition layers run words together).
2. **The merge** (`_with_unread_layer_lines`). A remaining layer line is appended after the
   OCR text unless the OCR text already holds the whole line: the same characters in the
   same order, starting and ending at token boundaries (a line may skip punctuation that
   leads or trails an OCR token, but never a currency sign, minus or percent sign).
   Spacing next to a letter is not compared, because layers and OCR break words
   differently ("EffectiveDate", "of39"); spacing between digits and punctuation is ("1
   2" is not "12"). Quote and dash variants compare equal. Lines with a control character
   (a garbled font) or without a letter or digit are never appended, as before.

### Invariants

Stated and tested in `tests/test_ocr_layer_line_properties.py` (Hypothesis, against
brute-force references written without the implementation's offset bookkeeping):

- R1 to R5 for the recognition filter: its result is a subsequence of the input; every
  painted line is kept; an invisible line is dropped only as a fragment or as part of a
  failed layer (checked against a written-out definition); more OCR text never drops a
  kept line; applying it to its own result changes nothing.
- M1 to M8 for the merge: the OCR text is a prefix of the result, which is the OCR text
  exactly when nothing is appended; every layer line with a letter or digit and no
  control character is held by the result; nothing is appended when OCR read every line
  (lines cut from OCR's own tokens, respaced next to letters, trimmed of edge punctuation,
  quote and dash variants swapped); the appended lines are exactly the unread ones, once
  each, in layer order; merging twice changes nothing; with blank OCR the layer is
  returned unchanged; more OCR text never appends more; every line #854's rule appended
  is held by the result unless the filter dropped it as a recognition line.
- Together: every painted layer line with a letter or digit and no control character is
  in the page text.

`tests/test_documents_ocr_overlay.py` builds PDFs with filled, stroked, render-mode-3 and
transparent text. The 19 pages in `tests/fixtures/ocr_overlay/` are run through
`_pdf_page_text` on the retained PDFs (checked by SHA-256) with Tesseract's stored output.
A mutation check (26 broken variants of the rule) is killed by these tests.

## Measurement

Every page the overlay rule reaches: the 1,041 pages in 328 retained PDFs of `ocr: true`
manifest documents listed by #853's sweep (`ocr-rule-sweep-final.json`), all of them
read from retained bytes. Tesseract 5.5.3 (eng, 200 dpi) output was cached by the exact
rendered page image, so both rules read the same OCR text. Five pages have blank OCR text;
both rules return their layer unchanged.

### Pages

| | #854 | This change |
| --- | ---: | ---: |
| Layer lines appended | 671 | 944 |
| Typed or legible lines appended (words) | 513 (1,713) | 702 (2,329) |
| Junk lines appended (words) | 158 (453) | 242 (579) |
| Pages with junk appended | 88 | 88 |
| Pages missing a legible layer word (words) | 20 (33) | 1 (1) |

367 pages in 160 PDFs append different lines. Of the 182 lines #854 appended that are no
longer appended, 138 are lines OCR read with other spacing or quote style (41 of them the
ND-20-0004 footer), and 44 are noise from failed recognition layers (MT-13-0048-MM's
mirrored layer, NJ CHIP 22-0031, NJ-19-0009, UT-14-0007-MM, and the shifted signature
dates on ID-20-0001 and MO-20-0016).

"Missing a legible layer word" is the loss measure used for #864: a letter-only word of
five or more letters of the page's layer (lines without control characters), in the
system word or name list, that the page text lacks in any form (with spacing and
punctuation removed, or as a near-identical word). The one remaining word, "tint's", sits
in a noise line of NJ CHIP 22-0031's failed recognition layer.

"Junk" is a line that is not text a reader could use, by reviewed family: an invisible
recognition layer's misreadings and fragments, recognition over sideways scans
(UT-14-0007-MM, UT-14-0004-MM), text in a font whose codes are shifted ("%JSFDUPS" for
"Director"), and the visible OCR of screenshots in WV-23-0001. Each family was reviewed on
rendered pages.

The junk this change appends that #854 did not, 133 lines (276 words):

- 54 painted lines, which the rule keeps by design because nothing separates them from
  typed text: 39 in WV-23-0001 (a visible OCR layer over screenshots of an eligibility
  system) and 15 in shifted fonts with no control character on the line (CA-25-0037,
  AL-20-0004, MA-18-025, MA-20-0024, MO-20-0027, WA-19-0012, WA-20-0004).
- 79 invisible lines: 43 from UT sideways scans on pages whose layer has fewer than five
  words (too few to judge), 32 misreadings from layers that agree with OCR elsewhere
  (MD-19-0008, NJ CHIP 22-0031, a Uganda gazette page), and 4 in shifted fonts (IL-21-0006,
  WI-22-0009).

The two layers named in the defect report append nothing: UT-14-0007-MM page 21 ("ac al
ckm cl err", none of its words in the OCR text) and ID-20-0001 page 3 ("Ejhjubmmz", two
of eight words in the OCR text). Of the 185 invisible layers with at least five words, 15
share none of their words with OCR and 3 more share under 10%; 6 share 20% to 50%; the
other 161 share 50% or more, 116 of them 90% or more. The two layers just above the
one-third threshold (a Uganda gazette page at 38%, MD-19-0008 page 14 at 39%) hold
legible lines among their misreadings.

### Documents

Re-extracting the 327 manifest documents behind those PDFs with `_extract_blocks` under
#854's rule and this one, from the same OCR text: no error on either side; no block
count, heading or section label changes; 155 documents and 362 pages change (51,976 to
52,673 words on those pages). Every token of the old page text that the new one lacks,
even ignoring spacing, is noise from a failed recognition layer, except one en dash
(IA-20-0003 page 3, where the layer line is now read by OCR's hyphen).

## Scopes whose pages change

52 scopes, listed with their changed documents and pages in
[`2026-10-13-ocr-overlay-layer-lines-scopes.csv`](2026-10-13-ocr-overlay-layer-lines-scopes.csv):
the CMS Medicaid state plans of AK, AL, AR, CA, CO, CT, DC, GA, HI, IA, ID, IL, IN, KS,
LA, MA, MD, ME, MI, MN, MO, MT, NC, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, TN,
UT, VA, VT, WA, WI, WV and WY (`us-xx/policy/2026-09-13-medicaid-state-plan`); the CMS
CHIP state plans of CO, CT, ME, MS, MT, NE, NJ, PA and SD
(`us-xx/policy/2026-09-13-chip-state-plan`); and
`us-hi/regulation/2026-09-10-medicaid-state-eligibility-manual`.

PR #864 builds successor scopes (`<original>-r2026-10-13-hollow-roots`) for 51 of them
with #854's rule. Those successors must be rebuilt with this rule: in place while #864 is
unmerged, or as a further successor revision after it merges. The Hawaii eligibility
manual scope has no successor in #864.

## Follow-ups

- **Shifted-font layers.** On 24 pages a constant code shift (28 to 31) turns some
  control-character lines into text OCR read, so the font is offset from ASCII. Applied to
  the same pages' other control-character lines, it gives 1,110 lines OCR did not read, on
  17 pages: some typed values (OR-15-0006 "11/30/15", "12/10/15"; MA-20-0024 "09/30/20"),
  some still noise (CA-25-0037). Both rules drop them as control-character lines. Decoding
  such fonts would recover the typed values and the shifted lines above.
- **Sideways scans.** On UT-14-0007-MM's sideways slides Tesseract's own text is noise
  ("(uas)pjiy usoqun sjuerddy" for "Applicant's Unborn Child(ren)"). Orientation
  detection before OCR would read them.
