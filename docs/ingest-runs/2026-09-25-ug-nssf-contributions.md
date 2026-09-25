# Uganda NSSF Act ss. 10-12: transcription corrections

Supersedes `2026-07-08-ug-nssf-contributions` with
`2026-09-25-ug-nssf-contributions` and cuts `ug-rulespec-2026-09-25`, which
differs from `ug-rulespec-2026-07-12` only in that scope.

## Why

The July rows came from Tesseract at 300 dpi over the Fund's hosted scan of
the Laws of Uganda revised-edition pages (Cap. 230, volume pages 8214-8218).
They carried OCR misreads ("employce", "duc", "fifly", "Onand"), words cut at
the right margin ("monthly wa", "contributi", "to t"), running heads fused
into sentences ("... are paid, National Social Security Fund Act [Cap. 230.
8215 a standard contribution ..."), and a section 12 row that ran on through
all of section 13.

rulespec-ug quotes these rows. Its s.10 module and composed pipeline cite
"employee’s share ofa standard contributi of five percent", and its s.12
module cites "calculated from fifly cents". A pilot that ran the Axiom encoder
on these rows found 6 of 34 proof excerpts quoting scan damage
(`_partnerships/tbi-codify/out/09-nssf-pilot-REPORT.md` in the mirror
workspace).

## Source

| | |
| --- | --- |
| URL | https://www.nssfug.org/site/assets/files/1501/nssf_act_cap_230.pdf |
| sha256 | `61adbe80fd7e79883eec43a966fd1c88dfd837a62d05842661a38652b0abefb4` |
| Retrieved | 2026-09-25, byte-identical to the 2026-07-08 capture |
| Pages used | PDF pages 7-11 (volume pages 8214-8218) |

Re-running the unchanged July manifest with Tesseract 5.5.3 reproduces the
July provisions file byte for byte, so the corrections below are keyed to a
deterministic OCR output.

## What changed in the manifest

- `text_replacements`: 25 single-line corrections applied to each page's OCR
  text before segmentation. The header comment in
  `manifests/ug-nssf-contributions-official-documents.yaml` lists every one
  with its page and subsection.
- `drop_line_patterns`: the two running-head forms ("8216 Cap. 230.] National
  Social Security Fund Act" and "National Social Security Fund Act [Cap. 230.
  8215").
- `page_windows[0].stop_at_pattern`: ends the window at "13. Voluntary
  contributions".
- `metadata.transcription_note`: states the corrections on every row.
- `source_as_of`: 2026-09-25.

## How each correction was decided

**OCR misreads (15).** The scan's "e" is worn to a "c" shape throughout
("employcc", "duc", "docs"), and some word spaces are closed up ("ofa",
"Onand", "Forthe"). Each correction was checked on the page image rendered at
300 dpi. Independent Tesseract passes at 450 dpi (psm 6) and 600 dpi (psm 3)
read "engagement;", "fifty", "For the", "A member" and curly apostrophes where
the 300 dpi pass did not, which settled the semicolon in s.11(4)(b) and the
two straight apostrophes in s.11(5).

**Margin restorations (11).** On volume pages 8215 and 8217 the scan is cut
at the right margin. The PDF is a mixed raster: a JBIG2 text mask
(1944 x 1121 on page 8) over a low-resolution background. The mask ends at
the same edge as the visible page, so the missing letters are not in this
print. Each cut word is completed with the only word that fits the visible
letters and the grammar:

| Volume page | Subsection | Print | Completed |
| --- | --- | --- | --- |
| 8215 | 10(6) | on ar | on an |
| 8215 | 10(6) | his or he | his or her |
| 8215 | 10(6) | the total wage | the total wages |
| 8215 | 10(6) | information a | information as |
| 8215 | 11(1) | monthly wa | monthly wage |
| 8215 | 11(1) | contributi | contribution |
| 8215 | 11(1) | to t | to that |
| 8215 | 11(1) | any mor | any month, |
| 8217 | 12(1) | tha | that |
| 8217 | 12(1) | in respec | in respect |
| 8217 | 12(1) | this section t | this section by |

Three completions go beyond the visible letters: the plural "wages", "that"
rather than "the", and the comma after "month". Each follows the Laws of
Uganda 2000 revised edition (Cap. 222) at the same point, read in the
Laws.Africa consolidation served from `media.ulii.org` (orientation only;
the cited source stays the Cap. 230 print). An uncropped print of the 2023
revised edition would settle them. The Uganda Law Reform Commission's copy is
subscription-only, ULII pages are bot-gated, and the Parliament library record
returned "Access denied".

## Fidelity checks

- A word-level diff of the corrected ss. 10-12 against the 2000 edition shows
  only edition differences: numerals written as words ("fifteen", "five",
  "ten"), "instalments" for "installments", "re-assessment", "non-resident"
  and s.11(9), where the 2000 edition reads "The provisions of this section
  shall have effect notwithstanding the provisions of the Employment Act"
  and the Cap. 230 print reads "This section shall have effect
  notwithstanding the Employment Act". No misread survives.
- `tests/test_ug_nssf_contributions_transcription.py` pins:
  - the absence of every July damage fragment and running head;
  - the s.12 boundary;
  - each proof excerpt rulespec-ug will quote, as a verbatim substring;
  - that every margin restoration only appends to the printed text;
  - that the release swaps only this scope.

## The July capture stays

`2026-07-08-ug-nssf-contributions` is not deleted. `ug-rulespec-2026-07-10` and
`ug-rulespec-2026-07-12` are published and name it, and CI's
`validate-release` job deep-validates every tracked selector against
`data/corpus`; deleting the scope fails both with `missing_provisions`,
`missing_inventory` and `missing_coverage` (checked locally before this
change was cut). The retirement precedent checked, the Alaska SNAP scope
(`2c197a2a4`), removed a scope that no selector names. The July rows stay
as the frozen content of those two releases. rulespec-ug stops citing them
when it re-pins to `ug-rulespec-2026-09-25`.

## Commands

```bash
uv run axiom-corpus-ingest extract-official-documents \
  --base data/corpus \
  --version 2026-09-25-ug-nssf-contributions \
  --manifest manifests/ug-nssf-contributions-official-documents.yaml
```

Coverage: 4 of 4 matched, complete.
