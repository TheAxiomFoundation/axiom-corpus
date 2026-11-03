# Arizona DES dated authority for the March 2026 SNAP ECE change

Date: 2026-10-09. Branch `ingest/az-des-ece-dated-authority`, cut from
`origin/main` d69a40575. Scope `us-az/manual/2026-10-09-az-des-snap-ece-dated-authority`.

## Why

Arizona's Nutrition Assistance (SNAP) expanded categorical eligibility (ECE)
gross-income limit was 185% of the federal poverty level (FPL) through benefit
month 02/2026 and 200% from benefit month 03/2026. TheAxiomFoundation/rulespec-us#1460
asks for a dated encoding: 1.85 through 2026-02-28 and 2.0 from 2026-03-01.

The current FAA5 pages are already released in `us-az/manual/2026-07-17-faa5-recovery`.
That scope states 200% (`na-categorical-eligibility/block-4` and `block-5`,
`na-eligibility-and-benefit-determination/block-5`). Every row carries
`expression_date` 2026-07-17, the capture date. No released row states the
185% rate or dates the change. One release cannot carry two rows at the same
citation path: axiom-corpus rejects the release (`duplicate_release_citation`),
and axiom-encode raises `AmbiguousCorpusSourceError`. Dated history therefore
needs a document at its own path. Its metadata must name the FAA5 pages as
amendment targets, and it must be a `us-az`/`manual` row, because axiom-encode
only looks for amendment rows in the target's jurisdiction and document class.

## Official source and access

DES published a "What's Changed on 03/23/2026" notice for its Cash and
Nutrition Assistance Policy (CNAP) Manual and later filed it under
`Archived_Policy/baggage/`.

- `source_url`: <https://dbmefaapolicy.azdes.gov/Archived_Policy/baggage/2026-03-23_What'sChanged.pdf>
- `download_url`: the Internet Archive capture of that URL,
  <https://web.archive.org/web/20260417195741id_/https://dbmefaapolicy.azdes.gov/Archived_Policy/baggage/2026-03-23_What'sChanged.pdf>

`dbmefaapolicy.azdes.gov` answered a plain request on 2026-10-09 with HTTP 403
and `Cf-Mitigated: challenge` (Cloudflare). This run did not use the
extractor's `request.browser_impersonation` against DES, and did not use
`local_path`. The bytes come only from the Internet Archive.

The Internet Archive CDX index lists three captures of the notice. All share
payload digest `UJIAFW65IDNJ7HBLBST5WHPJZMCHICLJ` (SHA-1, base32):

| capture | URL form | status |
|---|---|---|
| 20260417195741 | `2026-03-23_What'sChanged.pdf` | 200 |
| 20260710061041 | `2026-03-23_What%27sChanged.pdf` | 200 |
| 20260711083635 | `2026-03-23_What%27sChanged.pdf` | revisit |

The bytes fetched from the first capture (104,460 bytes) have SHA-1 base32
`UJIAFW65IDNJ7HBLBST5WHPJZMCHICLJ`, matching the CDX record, and SHA-256
`f8173335f1f7f73467020ed8a13d0e7ad2efd5a92d83f74f7c471b57d27232e3`. That
SHA-256 is the one axiom-encode#1760's coverage matrix records for this notice.
The matrix also records that a later fetch of the live DES URL returned the
same bytes. The extractor's stored source file has the same SHA-256.

PDF metadata: title "What's Changed on 03/23/2026", 4 pages, created
2026-03-24 10:32 EDT by Chrome (Skia/PDF). The text layer is clean.

The notice's ECE section reads:

> Change: NA Expanded Categorical Eligibility
> EFFECTIVE DATE: For the benefit month of 03/2026 and ongoing
> … The gross income limit for the NA ECE has changed from 185% of the FPL to
> 200% of the FPL.
> NOTE The gross income limit for the NA ECE change from 185% of the FPL to
> 130% of the FPL, announced on 02/23/2026, has been recalled.

It lists the revised references FAA3.D06D.01, FAA5.I01A (NA Eligibility and
Benefit Determination), FAA5.I01B (NA Categorical Eligibility), FAA6.A03J and
FAA6.J02B.04, each "(Updated as of 03/23/2026; Effective 03/01/2026)". The
notice's other items are an EBU/OPU unit merger, a budgetary-unit verification
reminder and a forms update. They are part of the document and are kept.

## Scope

Version `2026-10-09-az-des-snap-ece-dated-authority`; jurisdiction `us-az`;
class `manual`; manifest `manifests/us-az-des-snap-ece-dated-authority.yaml`;
one document, 2 rows:

- `us-az/manual/des/archived-policy/2026-03-23-whats-changed`: the document
  row, level 1, no body.
- `us-az/manual/des/archived-policy/2026-03-23-whats-changed/document-1`:
  level 2, the whole notice, 7,582 characters
  (`extraction: segmentation: single_block`).

Coverage is complete: 2 inventory items, 2 provisions, 0 missing, 0 extra.

**Path.** Existing AZ DES paths slug the publisher's own path (`FAA5/X.html`
becomes `des/faa5/x`). DES files this notice under `Archived_Policy/`, so the
path is `des/archived-policy/<date>-whats-changed`. The path collides with no
locked or manifest `us-az/manual` path. It stays out of `des/faa5/`, which
mirrors the live FAA5 table of contents. `document-1` is in neither the
`block_n` nor the `page_n` citation-path ratchet.

**Single block.** axiom-encode shows one row per amendment document: the
marked body row with the fewest path segments. It does not join child blocks.
It omits a body over 12,000 characters entirely. A per-page split would show
the model only page 1, and the ECE section is on page 2.

**Dates.**

- `expression_date` is 2026-03-23, the notice's own date.
- `metadata.effective_start` is 2026-03-01, the first day of benefit month
  03/2026, with the notice's wording in `metadata.effective_basis`.
- `source_as_of` is 2026-04-17, the capture date.
- `metadata.expression_date_note` records this choice.

**Amendment metadata.** These keys are copied onto both rows:

- `amends`: bare citation paths of the two pages,
  `us-az/manual/des/faa5/na-categorical-eligibility` and
  `us-az/manual/des/faa5/na-eligibility-and-benefit-determination`.
- `amendment_targets`: the three blocks that state the rate, categorical
  `block-4` and `block-5` and eligibility `block-5`.
- `document_type`: `policy change notice (amendment)`.
- `amendment_summary`: one prose sentence.

Archive provenance: `archived_official_source`, `archive_url`,
`archive_timestamp`, `archive_payload_sha1_base32`, `archive_payload_sha256`.

## How axiom-encode attaches it

This was read at axiom-encode `origin/main` 81db3bd8a (0.2.2153).

- A row is an amendment row if its metadata has the key `amends`, or a
  `document_type` containing "amendment" (`src/axiom_encode/harness/evals.py`
  1879-1883).
- Target values come from `amends`, `amendment_targets` and related keys
  (1886-1896).
- A bare path matches structurally, across scope versions, when its segments
  start with the target's document path. For a block target, the document
  path is the longest common prefix of the rows that share the target's source
  file, here the page path (1967-2003, 2127-2143).
- Candidate rows come only from the pinned release, in the target's
  jurisdiction and document class (6371-6376).
- Matched documents are rendered newest first as
  `context/amendment-act-N.txt`, under "Post-consolidation amendment acts in
  this corpus scope". The prompt tells the model to "Encode amendment-supplied
  values as effective-dated `versions`", with proof atoms citing the amendment
  (10394-10409, 10909-10922).
- Every ISO date in the rendered file becomes a "Temporal scaffold date", and
  the model is told to prefer the earliest relevant one (14439-14451).

**Executed check.** I ran `_target_document_citation_path`,
`_discover_amendment_documents`, `_render_injected_context` and
`_collect_scaffold_dates` from an export of axiom-encode 81db3bd8a. The input
rows were the released recovery provisions (SHA-256
`8175940d284808c43222bc1a90328344f39fcb42f38b29581c162994535fc932`) and this
scope's provisions, with body-less rows dropped as
`iter_active_local_corpus_rows` drops them. Results:

| encode target | amendment documents attached |
|---|---|
| `…/na-categorical-eligibility/block-4` | `…/2026-03-23-whats-changed/document-1` (structured tier, expression date 2026-03-23) |
| `…/na-categorical-eligibility/block-5` | the same |
| `…/na-eligibility-and-benefit-determination/block-5` | the same |
| `…/na-medical-expenses-and-deduction/block-2` | none |
| `…/shelter-expenses-and-deduction/block-1` | none |

The rendered context file is 10,240 bytes, within the 32,000-byte aggregate
cap. Nothing was dropped and the body was not omitted. The scaffold dates are
2026-03-01, 2026-03-23 and 2026-04-17, so the earliest is the effective date.

The notice attaches to every block of the two pages, because matching is per
page, not per block. That is intended: the notice revises both pages.

## Candidates considered and not ingested

- **FAA6.J02B.04 "NA Expanded Categorical Eligibility Standard (185% FPL)",
  archived "_03-2026" PDF** (Internet Archive 20260417210829, SHA-1
  `M2ASJ2KUVGW2NX5THQEQ2Q3WW6CBYBXL`). Its embedded font has no usable text
  layer (pdftotext output is unreadable), so it would need OCR. It states the
  185% dollar table, not the change date.
- **FAA5.I01B NA Categorical Eligibility, Revision 54 PDF** (Internet Archive
  20260417203432, SHA-1 `5WDBXJ4AKYCVXHIOKEITKQWSMBI3WT6X`). This is the prior
  page text, with the same unusable text layer. As an amendment row, the
  encoder would present it as a "post-consolidation amendment act", which is
  backwards for superseded text.
- **FAA6 NA Expanded Categorical Eligibility Standard (185% FPL) HTML** (capture
  20251030220702) and **FAA5 FFY 2026 NA COLA Changes** (capture
  20251030220841, SHA-256
  `3dc09c5a979a5593585d05d543372acbef38dbd43616ea506db14e9932696daa`). Both are
  clean, but they state 185% "effective 10/01/2025". That is the FFY 2026 dollar
  update, not a change in the rate. As amendment rows they would also render as
  post-consolidation amendments and add a 2025-10-01 scaffold date earlier than
  the change. The notice already states the prior and new rates and the date.
  axiom-corpus#780's program bundle also excludes the COLA page as back-year.
- **`Archived_Policy/Work_Registration_and_Program_Determination.html`**, the
  FAA5 pages' "Prior Policy" change index. Its last Internet Archive capture is
  2025-10-30, before the change.
- **`Archived_Policy/WhatChangedHistory.html`**. Its 2026 capture is a
  redirect, and the last 200 capture is from 2025-10-31.

## Not ingested: the standard medical deduction increase

rulespec-us#1461 reports that FAA5 `NA_Medical_Expenses_and_Deduction.html`
now sets the standard medical deduction to $160 and that DES updated it on
2026-09-14. No route that this run could use reaches a dated official source:

- **Internet Archive.** CDX lists no capture of the FAA5 medical page after
  20251030220842, and no `Archived_Policy/baggage/2026-09*` file.
- **des.az.gov.** IA captures of `/esap` (2026-08-20) and of the Nutrition
  Assistance FAQ (2026-10-05) do not mention the medical deduction.
- **Live hosts.** `dbmefaapolicy.azdes.gov` and `des.az.gov` answer HTTP 403
  with `Cf-Mitigated: challenge`.

The released medical page (`2026-07-17-faa5-recovery`, block-2) still says $145.
This scope carries no SMD document.

## Commands

```bash
uv run axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-10-09-az-des-snap-ece-dated-authority --manifest manifests/us-az-des-snap-ece-dated-authority.yaml
```

The Internet Archive CDX index was queried at
`https://web.archive.org/cdx/search/cdx` (matchType exact and prefix). Captures
were fetched with `curl` from the `id_` URLs. Digests were computed with
`shasum -a 256`, and SHA-1 base32 with Python's `hashlib` and `base64`.

No release was published or activated, and nothing was loaded into Supabase by
this ingest. The release selector that adds this scope is a separate change.
