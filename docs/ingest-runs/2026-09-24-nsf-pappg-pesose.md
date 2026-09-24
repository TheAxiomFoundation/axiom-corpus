US NSF PESOSE and PAPPG 24-1 Chapters II and III corpus ingest reasoning

Impact basis:
- Encoding NSF proposal-compliance rules for PESOSE (NSF 26-506) proposals
  needs the solicitation plus the PAPPG chapters that govern proposal
  preparation (Chapter II) and post-submission processing (Chapter III).
- Chapter III.C (Proposal File Updates) sets when a proposal file update is
  accepted automatically, when it needs the cognizant NSF Program Officer's
  acceptance, and that post-deadline requests are limited to correcting a
  technical problem (formatting or print problems).

Governing version (verified live on 2026-09-24):
- https://www.nsf.gov/policies/pappg names NSF 24-1 as the current version and
  states that it applies to all proposals submitted or due on or after
  May 20, 2024. The replacement NSF Guidance on Financial Assistance was still a
  draft open for comment through Aug. 24, 2026.
- PAPPG 24-1 Supplement 1 (NSF 26-200) and Supplement 2 (NSF 26-202) apply to
  financial assistance awarded on or after Dec. 8, 2025 and Jan. 22, 2026.
  Supplement 1 revises Chapter III.B (minimum number of reviewers); neither
  supplement revises Chapter III.C. The supplements are not ingested here.

Official sources:
- NSF 26-506, Pathways to Enable Secure Open-Source Ecosystems (PESOSE):
  https://www.nsf.gov/funding/opportunities/pesose-pathways-enable-secure-open-source-ecosystems/nsf26-506/solicitation
- PAPPG 24-1 Chapter II, Proposal Preparation Instructions:
  https://www.nsf.gov/policies/pappg/24-1/ch-2-proposal-preparation
- PAPPG 24-1 Chapter III, NSF Proposal Processing and Review:
  https://www.nsf.gov/policies/pappg/24-1/ch-3-proposal-processing-review

Scope:
- `manifests/us-nsf-pappg-pesose-2026.yaml`, three documents under
  `us/guidance/nsf/...`, all retrieved 2026-09-24.
- Chapter III uses the same content selector and drop selectors as Chapter II
  (the two pages share one NSF layout-builder template). The extracted blocks
  follow the chapter's lettered sections; III.C is
  `us/guidance/nsf/pappg/24-1/chapter-iii/block-4`, and the chapter footnotes,
  including [54] and [55] cited by III.C, are
  `us/guidance/nsf/pappg/24-1/chapter-iii/block-15`.
- The III.C block text was compared with an independent fetch of the same page
  and matches it word for word.

Re-extraction check:
- NSF 26-506 and Chapter II were first extracted on 2026-08-30. Today's text
  was compared sentence by sentence with that extraction. The only differences
  are navigation, table-of-contents, and "Document History" strings that the
  narrowed selectors in this manifest deliberately drop; no source sentence
  changed.

Generated artifact:
- Command:
  `axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-24-nsf-pappg-pesose --manifest manifests/us-nsf-pappg-pesose-2026.yaml`
- The generic official-document extractor wrote every row; no corpus rows were
  written by hand.
- Coverage result: complete; 126 source inventory rows matched 126 provision
  rows (3 documents, 123 blocks); no missing, extra, or duplicate citations.

Higher-authority slice: 2 CFR 200.204 and 200.205
- Why: the PAPPG is agency guidance. An encoding of a PAPPG provision records
  which higher authority it checked before treating the guidance as the
  operative source, and that check needs a statute or regulation in the
  corpus. The tracked corpus had no 2 CFR part 200 text and no NSF Act
  (42 U.S.C. 1861 et seq.) sections. 2 CFR 200.204 (notices of funding
  opportunities) and 200.205 (Federal agency review of merit of proposals) are
  the Uniform Guidance's pre-award provisions on how agencies announce
  opportunities and review applications, the level directly above PAPPG
  Chapters II and III. The August 30 References Cited encoding checked
  2 CFR 200.204 against a page-sliced multi-section govinfo PDF; this slice is
  section-level text from the eCFR publisher.
- Publisher: eCFR Versioner API. `titles.json` on 2026-09-24 reported title 2
  up to date as of 2026-09-22 (latest amended 2026-08-17), so the scope uses
  `--as-of 2026-09-22 --expression-date 2026-09-22`.
- Commands:
  `axiom-corpus-ingest inventory-ecfr --base data/corpus --version 2026-09-24-nsf-slice --as-of 2026-09-22 --only-title 2 --only-part 200`
  then
  `axiom-corpus-ingest extract-ecfr --base data/corpus --version 2026-09-24-nsf-slice --as-of 2026-09-22 --expression-date 2026-09-22 --only-title 2 --only-part 200 --section 200.204 --section 200.205 --workers 1`
- Scope `2026-09-24-nsf-slice-title-2-part-200` (the adapter appends
  `title-2-part-200`; the `nsf-slice` qualifier marks it as a two-section
  slice, which a selector must not combine with a future full part 200 scope).
  Coverage complete: 4 provisions (part, subpart C, 200.204, 200.205), 0
  missing, 0 extra.

Not in this change:
- No R2 upload, Supabase load, named release, publication, or activation.
