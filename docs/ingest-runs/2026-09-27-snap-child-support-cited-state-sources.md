# SNAP child support elections: cited state primary sources

Date: 2026-09-27. Branch `ingest/snap-child-support-cited-sources`, based on
`origin/main` / `f1916d73b568616cbd0b4c3c26a92796835188d9`.

## Purpose

Retain the official state sources needed to encode the SNAP child support
option and its history from 2010: the income exclusion in 7 CFR 273.9(c)(17)
and the alternative deduction in 7 CFR 273.9(d)(5). The discovery checklist
is the policyengine-us child-support parameter and PR #9622; their claims are
not source text. This run follows axiom-corpus PR #736 and uses the corpus
manifest-driven `extract-official-documents` pipeline. Only live official
publishers were fetched. No archive service, mirror, USDA options report,
publication, R2 upload, Supabase load, signing, push, or pull request was used.

All source bytes and normalized rows are retained with source inventory and
coverage. The controller must review and sign ingest manifests after the
local commit; nothing under `.axiom/ingest-manifests/` is part of this change.

## Already in the corpus and confirmed

Pennsylvania's selected `us-pa/manual/2026-07-21-pa-snap-handbook` already has
both requested sources. At
`us-pa/manual/dhs/snap/560-income-deductions-560-6-child-support-deduction/block-1`,
560.61 states: "A household is eligible for a child support deduction from
net income before calculation of the shelter deduction if all of the
following conditions are met:". Block 3 prints "Reissued March 1, 2012,
replacing April 21, 2009". The scope's expression date is its 2026-07-21
retrieval date, not that reissue date.

`us-pa/manual/dhs/snap/560-income-deductions-560-appendix-a/block-1` through
`block-12` all contain "Child Support 7 CFR § 273.9(d)(5)". These blocks retain
the October 2025 through October 2014 tables; block 12 also carries the older
table. The amount language includes "The amount of the deduction is the
amount paid using the 4.0 conversion, not to exceed the amount of the court
ordered support." The live Appendix A was therefore not re-ingested. Its
official locator is
<http://services.dpw.state.pa.us/oimpolicymanuals/snap/560_Income_Deductions/560_Appendix_A.htm>.
Both existing passages are pinned in the new MD/PA/VT test.

Vermont's old `271-3Squares.pdf` URL returned HTTP 404 on 2026-09-27 with a
browser User-Agent (the plain client received HTTP 403). Searches of DCF's
official pages found no live replacement for that compilation. However,
[DCF's 2017–2023 adopted-rules index](https://dcf.vermont.gov/esd/laws-rules/proposed/archived-2017-21)
links [B18-06F](https://outside.vermont.gov/dept/DCF/Shared%20Documents/ESD/Rules-Adopted/B18-06F.pdf)
on the live official `outside.vermont.gov` host. That bulletin is included as
an additional rulemaking scope. It is not an archive-service capture even
though DCF labels its index "Archived Rules".

## Not ingested

- Vermont 3SquaresVT rules compilation:
  <https://dcf.vermont.gov/sites/dcf/files/ESD/Rules/2018/271-3Squares.pdf> —
  HTTP 404 with browser User-Agent on 2026-09-27; no live official replacement
  located. The archive-only rules and procedures captures cited by the
  parameter/PR remain excluded. B18-06F is live and is **not** in this exclusion.
- Iowa General Letter 7-F-81: the cited historical capture is archive-only;
  not fetched through an archive service.
- Massachusetts 106 CMR 363, Rev. 7/2009 capture: archive-only; not fetched.
- Maryland SNAP manual historical captures: archive-only; not fetched. This
  run adds the live COMAR chapter, not a reconstruction of those manuals.
- Pennsylvania 2009 and 2011 handbook captures: archive-only; not fetched.
  The existing live-source handbook rows above are confirmed separately.
- Arkansas FSC 2010 captures: archive-only; not fetched. The live 2020
  compilation supplies dated older pages but does not establish the entire
  manual's contents on every earlier date.
- Hawaii 2010 capture: archive-only; not fetched. The live DHS January 2014
  file is a distinct historical snapshot.
- USDA FNS SNAP State Options Reports: secondary summaries excluded by
  AGENTS.md and decision d325, including reports cited by the parameter/PR.
- Cornell LII, Justia, and other secondary copies: excluded. None was used to
  fill a source-text gap.

The archive-only items are discovery citations supplied by the task, not
live URLs tested in this run; no HTTP status is claimed for unrequested
archive-service URLs.

## Class, path, and vintage decisions

Compiled administrative rules use `regulation`, agency manuals use `manual`,
and agency letters/memoranda use the released jurisdiction's guidance family.
Registers and the Vermont repeal bulletin use `rulemaking`. New Jersey's
enacted session law uses `statute` with a session-law family distinct from
codified N.J.S.A. paths. Each official publication has its own version/scope;
Maryland's whole COMAR chapter is one scope containing its 62 regulations and
chapter history.

The Colorado, Rhode Island, Arkansas, and Hawaii historical sources append
`/vintage/<date>` to their source-family citation prefix. Their new versions
and dated citation paths can coexist with the current scopes in one release.
The vintage date identifies the source expression/compilation; it does not
assert that every sentence first became effective then. Printed effective
dates govern Colorado and Rhode Island. Arkansas and Hawaii lack a single
printed compilation-wide date, so their PDF creation dates identify the
vintage, explicitly labeled as file metadata rather than legal effective
dates. The section revision stamps remain in the bodies. This is a disclosed
exception to deriving dates from printed text; it avoids inventing a legal
effective date or labeling historical text with a 2026 expression date.

Maryland follows the released COMAR hierarchy
`us-md/regulation/title-07/subtitle-03/chapter-17/regulation-<number>`.
The previous chapter-03 scope was built with `extract-maryland-comar`, not an
official-documents manifest. Its adapter emits shared collection/title/subtitle
rows that collide with released scopes, so this run uses the required
official-document manifest and omits those shared ancestors. The chapter-17
document retains administrative history and authority; its `listed_regulations`
metadata independently records all 62 publisher-listed regulations, including
`.09-1`. The source index is retained byte-for-byte. The new manifest generator
derives the section list and latest printed effective amendment dates from that
index. No XML/GitHub mirror was substituted for DSD's live HTML publication.

The legacy DSD `.aspx` section URLs redirect to `regs.maryland.gov`; the
manifest uses the final official URLs and records the legacy locators.
`source_as_of` is retrieval date, while each Maryland `expression_date` is
the most recent printed effective amendment affecting that regulation,
including chapter-wide revisions. This does not claim original adoption on
that date. The latest chapter-wide revision is December 14, 2009; later
section amendments remain explicit. COMAR .35 states: "A household member who
has verification of having made legally obligated child support payments to
or for an individual living outside the household is allowed a deduction."
The extraction includes .30, .35, .42 and .43 in their entirety.

Vermont B18-06F has printed bulletin date December 10, 2018 and cover text
"CHANGES ADOPTED EFFECTIVE January 1, 2019". Its key continuation statement
is: "Current program options and waivers will be maintained (subject to
approval by the federal Food and Nutrition Service)." This is pinned on page 1.
It supports continuity across repeal; it does not itself identify the child
support election. All three pages have embedded text, including an existing
OCR layer on the scanned cover; the substantive paragraph is readable and
no new OCR was performed.

<!-- GENERATED_SOURCE_TABLE -->

<!-- SOURCE_DETAILS -->

## Citation-path ratchet and retention

<!-- RATCHET_RESULTS -->

The `.gitattributes` additions mark each new scope's retained HTML binary,
as in #736. PDF and DOCX retention follow the existing binary rules. Only
the new scopes' `sources/`, `inventory/`, `provisions/`, and `coverage/` paths
are force-added from the ignored `data/` tree; scratch downloads and the local
draft selector are not committed.

## Commands

The sandbox's default uv cache is not writable, so all successful uv commands
use these environment settings (not changes to repository configuration):

```bash
export UV_CACHE_DIR=/tmp/axiom-corpus-snap-cs-uv
export UV_PYTHON=/opt/homebrew/bin/python3.14
```

<!-- EXTRACTION_COMMANDS -->

Maryland's manifest is reproducible from its retained index:

```bash
uv run --extra dev python scripts/build_snap_child_support_md_manifest.py --index data/corpus/sources/us-md/regulation/2026-09-27-md-comar-07-03-17-snap/official-documents/md-comar-07-03-17-index.html --output manifests/us-md-comar-07-03-17-snap.yaml
```

## Verification

<!-- VERIFICATION_RESULTS -->

## Controller review questions

- Confirm that the disclosed PDF-creation-date convention for Arkansas and
  Hawaii is appropriate for these historical compilation scopes.
- Resolve election timing and hybrid calculations from the retained primary
  language in the rules repository. A source's use of "deduction" alone is
  not enough to classify the gross-income test.
- Review this committed reasoning log and extraction commands, then sign the
  scopes with the repository ingest key. No ingest manifest was signed here.
