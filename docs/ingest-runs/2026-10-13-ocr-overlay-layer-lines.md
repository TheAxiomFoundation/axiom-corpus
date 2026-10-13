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
paint and font name, unsplit. A span is painted when its characters are filled or stroked
(PyMuPDF `char_flags`) with non-zero opacity. If the spans do not hold the text output's
characters (whitespace and control characters aside; `sort_text` changes only the lines
the text output prints, not its characters), the text output's lines are used instead,
all counted as painted, so no typed text can go missing.

1. **Garbled fonts** (`_without_garbled_spans`). A span holding a control character other
   than tab, newline, carriage return, VT or FF is a garbled font's, and so is every span
   on its line in the same font: such a font maps some codes to control characters and
   the rest to other wrong characters (CA-25-0037's "5678", "9C<:"). Those spans are left
   out whole, before anything splits them (Python's `splitlines()` breaks lines at U+001C
   to U+001E and U+0085, and `split()` strips U+001F, so judged after splitting a shifted
   font's "2EQI\x1e" would pass as "2EQI"). Spans in other fonts on the line, such as a
   date typed beside a garbled label, are kept. A line is painted when one of its kept
   spans with visible characters is.
2. **Recognition layers** (`_without_failed_recognition_lines`). Painted lines are all
   kept. An invisible line (text render mode 3, or fully transparent) belongs to a
   recognition layer, an earlier OCR of the same image, not typed text. Two kinds are
   dropped: a fragment, fewer than three letters (counted before lower-casing, after NFKC)
   and no digit ("cc:", a stray "L"); and every invisible line of a failed layer, one
   with at least five distinct words of three or more letters of which fewer than a third
   occur in the OCR text (as one of its words, or, for words of six or more letters,
   inside its letters run together, since recognition layers run words together).
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
  whitespace is left out, with every span on its line in the same font; every other
  span's text is in its line, in order, with one space where left-out spans stood between
  kept spans; no line returned holds such a control character; a line is painted exactly
  when one of its kept spans with visible characters is.
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
- Together: the text of every painted span outside a garbled font, line by line, is in
  the page text wherever it has a letter or digit.

`tests/test_documents_ocr_overlay.py` builds PDFs with filled, stroked, render-mode-3 and
transparent text. The 20 pages in `tests/fixtures/ocr_overlay/` (19 named in the defect
report or measured below, and AL-20-0004 page 4, whose shifted span splits at U+001E) are
run through `_pdf_page_text` on the retained PDFs (checked by SHA-256) with Tesseract's
stored output, with and without `sort_text` and `ignore_actual_text`. A mutation check runs
35 broken variants of the rule against these tests; its result is recorded in the PR.

## Measurement

Every page the overlay rule reaches: the 1,041 pages in 328 retained PDFs of `ocr: true`
manifest documents listed by #853's sweep (`ocr-rule-sweep-final.json`), all of them
read from retained bytes. Tesseract 5.5.3 (eng, 200 dpi) output was cached by the exact
rendered page image, so both rules read the same OCR text. Five pages have blank OCR text;
both rules return their layer unchanged.

### Pages

| | #854 | This change |
| --- | ---: | ---: |
| Layer lines appended | 671 | 910 |
| Typed or legible lines appended (words) | 486 (1,684) | 673 (2,298) |
| Junk lines appended (words) | 185 (482) | 237 (581) |
| Pages with junk appended | 99 | 80 |
| Pages missing a legible layer word (words) | 20 (33) | 1 (1) |

365 pages in 159 PDFs append different lines. Of the 207 lines #854 appended that are no
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
recognition layer's misreadings and fragments, recognition over sideways scans
(UT-14-0007-MM, UT-14-0004-MM), text in a font whose codes are shifted ("%JSFDUPS" for
"Director", and shards of garbled spans), and the visible OCR of screenshots in
WV-23-0001. Each family was reviewed on rendered pages.

Junk this change appends that #854 did not: 126 lines (278 words).

- 47 painted lines, which the rule keeps by design because nothing separates them from
  typed text: 45 in WV-23-0001 (a visible OCR layer over screenshots of an eligibility
  system) and 2 shifted-font lines with no control character on their line (MA-20-0024
  "%JSFDUPS", WA-19-0012 "%FQVUZ %").
- 79 invisible lines: 43 from UT sideways scans on pages whose layer has fewer than five
  words (too few to judge), 32 misreadings from layers that agree with OCR elsewhere
  (MD-19-0008, NJ CHIP 22-0031, a Uganda gazette page and others), and 4 in shifted fonts
  (IL-21-0006, WI-22-0009).

Junk #854 appended that this change does not: 74 lines (179 words): 26 garbled-font
shards, 29 misreadings and 19 sideways-scan lines from failed layers.

The two layers named in the defect report append nothing: UT-14-0007-MM page 21 ("ac al
ckm cl err", none of its words in the OCR text) and ID-20-0001 page 3 ("Ejhjubmmz", two
of eight words in the OCR text). Of the 185 invisible layers with at least five words, 15
share none of their words with OCR and 3 more share under 10%; 6 share 20% to 50%; the
other 161 share 50% or more, 116 of them 90% or more. The cut-off sits in a flat range
(`scripts/threshold_eval.py`, final code): 0.15, 0.25, one third and one half gate 18, 19,
20 and 24 layers, holding 106, 109, 113 and 141 unread lines. One third gates one layer
more than 0.25, ID-20-0001 page 3; one half would add a Uganda gazette page (38%),
MD-19-0008 pages 14 and 5 (39%, 41%) and DC-16-0012 page 15 (48%), which hold legible
lines among their misreadings.

### Documents

Re-extracting the 327 manifest documents behind those PDFs with `_extract_blocks` under
#854's rule and this one, from the same OCR text: no error on either side; no block
count, heading or section label changes; 154 documents and 360 pages change (51,235 to
51,903 words on those pages). Every token of the old page text that the new one lacks,
even ignoring spacing, is a garbled-font shard or noise from a failed recognition layer,
except one en dash (IA-20-0003 page 3, where the layer line is now read by OCR's hyphen).

## Scopes whose pages change

52 scopes whose extracted documents change, listed with their changed documents and
pages in
[`2026-10-13-ocr-overlay-layer-lines-scopes.csv`](2026-10-13-ocr-overlay-layer-lines-scopes.csv):
the CMS Medicaid state plans of AK, AL, AR, CA, CO, CT, DC, GA, HI, IA, ID, IL, IN, KS,
LA, MA, MD, ME, MI, MN, MO, MT, NC, ND, NE, NH, NJ, NM, NV, NY, OH, OK, OR, PA, RI, TN,
UT, VA, VT, WA, WI, WV and WY (`us-xx/policy/2026-09-13-medicaid-state-plan`); the CMS
CHIP state plans of CO, CT, ME, MS, MT, NE, NJ, PA and SD
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

- **Shifted-font layers.** On 24 pages a constant code shift (28 to 31) turns some
  control-character lines into text OCR read, so the font is offset from ASCII. Applied to
  the same pages' other control-character lines, it gives 1,110 lines OCR did not read, on
  17 pages: some typed values (OR-15-0006 "11/30/15", "12/10/15"; MA-20-0024 "09/30/20"),
  some still noise (CA-25-0037). Both rules drop them as control-character lines. Decoding
  such fonts would recover the typed values and the shifted lines above.
- **Sideways scans.** On UT-14-0007-MM's sideways slides Tesseract's own text is noise
  ("(uas)pjiy usoqun sjuerddy" for "Applicant's Unborn Child(ren)"). Orientation
  detection before OCR would read them.
