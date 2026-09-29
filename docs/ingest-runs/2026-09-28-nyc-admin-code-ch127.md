# NYC Administrative Code §§ 11-1701, 11-1704.1 and 11-1706 after chapter 127 of 2026

Date: 2026-09-28 (capture), committed 2026-09-29. Branch `ingest-nyc-admin-code-ch127`, cut
from `origin/main` dbb69efb8. First part of TheAxiomFoundation/axiom-corpus#766, the
blocker for TheAxiomFoundation/rulespec-us#1438. The PolicyEngine side of the same change is
PolicyEngine/policyengine-us#9664.

## Problem

The only NYC Administrative Code scope, `us-ny/statute/2026-06-05-nyc-admin-code`
(`source_as_of` 2026-06-05), still has the text from before chapter 127 of the Laws of
2026 (A.11561, Part D, signed and effective 2026-06-05). Chapter 127 moved the switch from
the § 11-1701(a) resident rates to the lower (b) rates from 2027 to 2030. It also extended
the § 11-1704.1 14% additional tax on the same schedule. Every US release selector that
carries NYC Administrative Code text selects that stale scope. That includes
`us-rulespec-2026-08-08-obbb-alien-snap`, which rulespec-us pins, and its successor
`us-rulespec-2026-09-24-snap-fy2027-cola`. The encoder reads provision text only from the
pinned signed release, so the #1438 re-encode cannot start until a release carries the
amended text.

## Official source and access

The publisher is American Legal Publishing's Code Library, the source of the 2026-06-05
scope. Its "September 2026 (current)" edition carries the amended text. Both amended
sections have the history note "Am. 2026 N.Y. Laws Ch. 127, 6/5/2026, eff. 6/5/2026".

| Section | Page (`source_url`) |
|---|---|
| § 11-1701 | <https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13463> |
| § 11-1704.1 | <https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13565> |
| § 11-1706 | <https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCadmin/0-0-0-13608> |

These are the adapter's default URLs (`DEFAULT_NYC_ADMIN_CODE_SECTIONS`). CodeLibrary sits
behind a Cloudflare challenge and answers HTTP 403 to `curl`, so the pages were captured on
2026-09-28 in Chrome, not signed in to CodeLibrary, through the Claude in Chrome extension.
Each page was opened in the browser. A same-origin `fetch(location.href)` from that page
then took the server's HTML response, which was saved byte for byte through a browser
download. That is the page as served, before any script runs. The retained 2026-06-05
files have the same form: every file in both captures has 242 CRLF lines and carries the
section body in the served HTML, and the sizes are close (see below).

One fetch made with `cache: 'no-store'` got the 6,338-byte Cloudflare challenge page
(`cf-mitigated: challenge`) instead of the section and was discarded. Each retained file was
checked to contain the `codenav__section-body` element and to have no `cf-mitigated`
header. The retained responses carry `Date` headers of 20:42:27 (§ 11-1701), 20:43:21
(§ 11-1704.1) and 20:43:33 UTC (§ 11-1706).

| Retained source (`data/corpus/sources/us-ny/statute/2026-09-28-nyc-admin-code/nyc-admin-code-amlegal-html/...`) | Bytes | SHA-256 | 2026-06-05 bytes |
|---|---:|---|---:|
| `11-1701/0-0-0-13463.html` | 420,563 | `91203a113dc9489097171d6ea13ec2f847cb87b9a50b33b8ce04e057786f1737` | 420,212 |
| `11-1704.1/0-0-0-13565.html` | 178,827 | `7440bfbbcdd1dbc3d8c969e44a2eed11eefb77ef9e943a48d6c7359459d92294` | 178,626 |
| `11-1706/0-0-0-13608.html` | 420,160 | `ab3d16c0510243ee361d3e7c2384522e7df9d08693dcb0302bc8cdf31c58a5d2` | 404,061 |

The source caveat on every row is unchanged. CodeLibrary is a compilation, so for
evidentiary use the text should be checked against the session law. The check against the
session law follows.

## Cross-check against the session law

A.11561 as passed, <https://legislation.nysenate.gov/pdf/bills/2025/A11561>, fetched on
2026-09-28: 13 pages, SHA-256
`52179cd4bea441c790c5aed2c49cdcae959a66d3569bfde9e3e374e0e4bf6d34`. Part D § 6 (page 8,
line 48 to page 9, line 6) amends the § 11-1701 opening paragraph. § 7 (page 9, line 7
to page 10, line 8) re-enacts § 11-1701(b). § 8 (page 10, lines 9-23) amends
§ 11-1704.1(a)(1). A word-level diff of each new body against the 2026-06-05 body finds
only these changes:

- **§ 11-1701** (365 lines, as before):
  - Opening paragraph. Subdivision (a) now applies "before two thousand thirty" (was
    "twenty-seven"). Subdivision (b) now applies "after two thousand twenty-nine" (was
    "twenty-six"). The proviso now reads "for any taxable year beginning after two thousand
    twenty-nine" (was "twenty-six").
  - The (b)(1), (b)(2) and (b)(3) table headers now read "For taxable years beginning after
    two thousand twenty-nine:" (was "twenty-six").
  - In (b)(1) and (b)(3), "jointly with [his or her] such individual's spouse". The bill
    makes this change too (page 9, lines 15 and 46).
  - The history note gains the chapter 127 entry.
  - The (b) table values are unchanged and equal the bill's: 1.18%, and bases of $255,
    $591 and $1,245 / $170, $394 and $830 / $142, $328 and $692.
  - Subdivision (a) is not amended.
- **§ 11-1704.1** (65 lines, as before): paragraph (a)(1) now reads "before two thousand
  thirty" (was "twenty-seven"), and the history note gains the chapter 127 entry.
- **§ 11-1706** (291 lines, now 301): chapter 127 does not amend it. The capture does pick
  up a later amendment, with the history note "Am. L.L. 2026/133, 8/18/2026, retro. eff.
  1/1/2026".
  - Subdivision (c)(2)(A), the credit for unincorporated business taxes paid, now has three
    schedules:
    - (i) 1997 through 2006: 65% to 15%;
    - (ii) 2007 through 2025: 100% to 23%;
    - (iii) from 2026: 100% to 23%, then 23% down to 15% between $1,000,000 and
      $1,250,000 of city taxable income.
  - The amounts are now written in numerals ("$42,000", "65 percent") where the old text
    spelled them out.
  - Nothing else in the section changed.

In § 11-1701 the phrases "two thousand twenty-six" and "two thousand twenty-seven" no longer
appear. `tests/test_us_ny_nyc_admin_code_ch127.py` pins every change listed above.

## Scope

- Version `2026-09-28-nyc-admin-code`, jurisdiction `us-ny`, class `statute`.
- Three `section` rows: `us-ny/statute/NYC/11-1701`, `/11-1704.1` and `/11-1706`. Each is
  level 1, has no parent, and has `source_as_of` = `expression_date` = 2026-09-28. The row
  shape and key set match the 2026-06-05 rows, and so do the citation paths, labels,
  headings and metadata. Row ids are derived from the new version.
- Coverage is complete: 3 sources, 3 provisions, 0 missing, 0 extra.

`expression_date` follows the adapter default and the 2026-06-05 scope's convention, which
is the capture date. The text has been in force since chapter 127 took effect on 2026-06-05.
The 2026-06-05 scope already uses that date for the unamended text, however, so reusing it
here would give the same expression date to two different texts.

## Adapter fix: no dangling parent

`extract_nyc_admin_code` set `parent_citation_path="us-ny/statute/NYC"` on every row but
never emitted a `us-ny/statute/NYC` row. Release validation rejects that as
`missing_parent_citation`. Commit 3b6989cf2 ("Repair local release-artifact debt") removed
the dangling links from the 2026-06-05 artifacts but did not fix the adapter. A fresh
extraction therefore reproduced the defect. The adapter now leaves the parent unset,
which is the shape of the 2026-06-05 rows. The existing unit test asserts it.

GitNexus impact analysis could not run. Its index reports a storage-version mismatch:
database file version 42, build storage version 40. Callers were checked by hand with
`git grep`. `extract_nyc_admin_code` is called only by `_cmd_extract_nyc_admin_code`
(`extract-nyc-admin-code`) and the tests. No released artifact is rewritten.

## Supersession

The new scope carries the same three citation paths as `2026-06-05-nyc-admin-code`.
Therefore:

- **A release must select exactly one of the two NYC scopes.** Under
  `complete-expression-dates-v1`, selecting both fails `duplicate_release_citation`.
  `axiom-encode` resolves a citation only within the pinned release's scopes and raises
  `AmbiguousCorpusSourceError` on more than one match (`corpus_resolver.py` on `origin/main`,
  around lines 567-613).
- **The next US cut on the rulespec-us pin line swaps them.** It must select this scope in
  place of `us-ny/statute/2026-06-05-nyc-admin-code`. Every later US cut must keep the swap,
  or a later re-pin would bring the stale text back.

The selector is cut in a separate pull request, as the SNAP FY 2027 ingest (#745) and its
selector (#747) were.

## Commands

```bash
# Browser-saved pages under <saved>/nyc-admin-code-amlegal-html/<section>/<page-id>.html
uv run axiom-corpus-ingest extract-nyc-admin-code --base data/corpus --version 2026-09-28 \
  --section 11-1701 --section 11-1704.1 --section 11-1706 \
  --source-as-of 2026-09-28 --expression-date 2026-09-28 --source-dir <saved>
```

The adapter appends `-nyc-admin-code` to `--version`. `--version 2026-09-28` therefore
writes the scope `2026-09-28-nyc-admin-code`, just as `--version 2026-06-05` produced the
earlier one. `--source-dir` reads only local files and makes no publisher request. Since
the retained sources sit at the same relative paths, rerunning the command with
`--source-dir data/corpus/sources/us-ny/statute/2026-09-28-nyc-admin-code` reproduces the
scope byte for byte, and a test checks exactly that.

The artifacts sit under the ignored `data/` tree, so the content commit force-adds the
scope's `sources/`, `inventory/`, `provisions/` and `coverage/` paths. `.gitattributes`
marks the retained HTML binary, as for other retained HTML.

## Signing

This manifest attests this note as its reasoning log by SHA-256. `guard-ingested` requires
the signing commit to be an ancestor of the guarded head. The signature is therefore made
from the clean content commit, after the last edit to this note, and committed on its own.
The ingest private key is read from the agent secret store into the environment and never
printed:

```bash
uv run --extra dev axiom-corpus-ingest sign-ingest-manifest --repo . --base data/corpus \
  --jurisdiction us-ny --document-class statute --version 2026-09-28-nyc-admin-code \
  --command "uv run axiom-corpus-ingest extract-nyc-admin-code --base data/corpus --version 2026-09-28 --section 11-1701 --section 11-1704.1 --section 11-1706 --source-as-of 2026-09-28 --expression-date 2026-09-28 --source-dir <browser-saved CodeLibrary HTML>" \
  --reasoning-log docs/ingest-runs/2026-09-28-nyc-admin-code-ch127.md
```

## Verification

- `extract-nyc-admin-code`: 3 provisions, `coverage_complete: true`, 0 errors, 0 skipped
  sources.
- `validate-release` on a scratch selector holding only this scope, under profile
  `complete-expression-dates-v1`: `ok: true`, 0 errors, 0 warnings. The same capture extracted with
  the old adapter gives three `missing_parent_citation` errors and three `missing_parent_id`
  warnings.
- `tests/test_us_ny_nyc_admin_code_ch127.py` and `tests/test_corpus_nyc_admin_code.py`
  pass. They check:
  - byte-identical re-extraction from the retained HTML;
  - source hashes against the inventory;
  - the row shape;
  - each chapter 127 change in §§ 11-1701 and 11-1704.1;
  - the Local Law 133 text in § 11-1706;
  - that the 2026-06-05 scope still has the pre-amendment text.
- `scripts/validate_citation_paths.py`: OK.

## Not done here

- The release selector, publication, re-pinning rulespec-us, and the #1438 re-encode. The
  re-encode runs through `axiom-encode encode ... --backend codex --apply` on a subscription
  lane.
- NY Tax Law §§ 1301, 1304 and 1304-B. Chapter 127 Part D §§ 2-4 amends this state enabling
  law in the same way. #766 lists its ingest as optional, and it would need its own
  `extract-new-york-openleg-sections` scope. On rulespec-us `origin/main`, no `us-ny` module
  cites Tax Law § 1301, § 1304 or § 1304-B.
- rulespec-us's `us-ny/statutes/NYC/11-1706.yaml` defers
  `unincorporated_business_tax_credit`. So the Local Law 133 schedule changes no encoded
  value, but the module's source text changes when rulespec-us re-pins.
