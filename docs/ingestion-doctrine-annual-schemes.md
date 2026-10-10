# Annual-scheme ingestion doctrine

Internal register for developers and agents ingesting schemes adopted, retained,
or revised on a recurring cycle. Typical scopes include UK council schemes, US
state plans, and similar local instruments whose rules and annual legal authority
may appear in different official records.

## Controlling rule

Treat an annually adopted scheme as a controlled incorporation problem. A prior
instrument may supply substantive text for a later period only when a timely final
decision by the competent body unambiguously incorporates it, identifies the
operative period, and either makes no substantive changes or supplies determinate
evidence for every change used by the encode.

The operative basis may therefore be a resolution rather than a newly issued
instrument. In an annual re-adoption:

- the resolution supplies authority for the target year;
- the incorporated instrument supplies unchanged substantive rules; and
- an adopted report, schedule, table, or other record supplies amendments.

Read these records as one closed corpus. Do not infer annual operation from a
current publication page, a recently uploaded PDF, or an instrument's continued
availability. Publication corroborates identity; it does not perform adoption.
Each encoded rule must cite the record that establishes it. A rule changed by the
annual decision should cite both the base text and the modifying record.

## Identification-chain register

Trace an official, unbroken chain from the final adoption act to the substantive
text. A common chain is:

```text
final minutes or decision record
  -> adopted recommendation
  -> named report
  -> identified scheme, appendix, schedule, or table
```

Record one of these classifications:

| Classification | Use when | Example |
| --- | --- | --- |
| `ACCEPT` | The adopted material identifies the exact instrument or appendix. | Council adopts “Appendix A, 2026/27 Council Tax Reduction Scheme.” |
| `ACCEPT-DERIVED` | “Current” or “existing” is resolvable through the adopted material to one prior decision, title, date, appendix, or official URL. | Final minutes adopt a report whose recommendation retains the scheme adopted by Full Council on a named date. |
| `REJECT` | Selecting the instrument requires an assumption or a separately discovered PDF. | Minutes say “continue current arrangements,” while several editions are published and none is linked by the adopted record. |

For `ACCEPT-DERIVED`, preserve every intermediate document and state the derivation
in manifest metadata. Search-engine proximity, matching subject matter, or a
plausible filename does not repair a broken link.

The adopted record, directly or through expressly incorporated text, should state
verbatim:

- final status, such as “resolved,” “approved,” “adopted,” or “agreed”;
- the target year, dates, or a longer operative period covering the target year;
- the scheme and, where relevant, the claimant or program population;
- a present continuation, retention, adoption, revision, or replacement act;
- whether the scheme is unchanged, uprated, or amended;
- the adopting body; and
- the final decision date.

“Recommended,” “proposed,” “to consider,” “subject to approval,” and approval to
consult are not final adoption wording. A statement that one policy feature will
continue does not incorporate the rest of a scheme.

## Operative-body gate

Verify the body legally empowered to make the annual decision. For English council
tax reduction schemes, use the final Full Council act unless an alternative lawful
route is affirmatively established. Cabinet, a committee, scrutiny, an executive
member, or an officer may recommend, prepare, or implement a scheme; those acts do
not substitute for Full Council adoption.

Apply the equivalent competent-body test in other systems. For a US state plan,
for example, distinguish an agency's final approval or submission from a working
group recommendation, proposed plan, or public-comment draft. Record the body,
decision status, decision date, and applicable deadline rather than inferring
authority from the document title.

Use final minutes or an official decision notice. Treat draft minutes as
provisional unless the body's governance rules make another published record
effective before approval of the minutes. Preserve recommendations and meeting
packs when they identify what was before the operative body, but cite the final act
for the target-year authority.

## Amendment tripwire

Stop the simple base-instrument-plus-resolution path when adopted material uses
language such as:

- “with the following amendments,” “subject to amendments,” or “as amended”;
- “uprate,” “reset,” “replace,” or “revised scheme”;
- new bands, rates, contribution levels, deductions, or exemptions;
- CPI, minimum-wage, or other indexed changes; or
- delegated insertion, selection, or rounding of figures.

An amendment hit requires the adoption record in the corpus. The encode must draw
amended values from that record, an adopted schedule, an implemented official
table, or a consolidated instrument—not from the superseded base instrument.
Retain the base instrument only for rules that the annual material leaves
unchanged.

A mechanical uprating may use a base-plus-overlay construction when the official
records make the formula, reference period, resulting figures, and authority
determinate. If an officer selected or rounded a value, ingest the implemented
official table or other record of that value. Use `REJECT` when an encoded value
would depend on an unavailable amendment or undocumented implementation.

Cambridge illustrates the boundary: the 2023 working-age instrument can ground
unchanged rules, while the 2026/27 Full Council adoption and its incorporated
recommendations ground annual uprating and the £8.36 UC non-dependant amount. The
Cabinet recommendation alone is not the operative act, and the case is not an
unchanged two-document continuation.

## Multi-document scope construction

Place every document needed to resolve the chain in one official-document manifest.
Give each source a stable `source_id` and a role that explains its legal function.
The Cambridge pilot uses:

- `scheme_text` for the incorporated substantive instrument;
- `operative_adoption` for the final Full Council minutes; and
- `adoption_confirmation` for the official decisions sheet.

Add other roles, such as `adopted_report`, `amendment_schedule`, or
`implemented_table`, when the scope requires them. In `identification` metadata,
express links such as `adopted_by`, `adopts`, `confirmed_by`, and
`carries_amendments`. Record the `ACCEPT` or `ACCEPT-DERIVED` classification and a
short human-auditable chain. Corroboration-only records must not be presented as
the adopting act.

Keep these years distinct:

- `base_instrument_year`: the year or commencement vintage of the incorporated
  scheme text; and
- `effective_scheme_year`: the annual period supported by the adoption corpus.

For example, a 2023 base instrument can participate in a scope whose
`effective_scheme_year` is `2026-2027`. Set the expression date for the period the
scope represents; do not redraft the base instrument's date to make it appear
newer.

Separate populations and scheme limbs explicitly. Do not silently combine UC,
non-UC working-age, pension-age, discretionary, or other variants merely because
they appear in the same meeting item.

## Retrieval and extraction mechanics

Verify before ingesting. Open each official URL, confirm the authority, document
identity, status, meeting body, date, target period, and relevant adopted wording,
then compare the bytes and extracted text with what the manifest describes.
Preserve fetched bytes, hashes, final URLs, and retrieval dates; mutable URLs can
later serve different content.

Committee-management portals may reject ordinary HTTP clients based on browser or
TLS fingerprints. Set `request.browser_impersonation: true` for those manifest
documents when the ordinary fetch and browser user-agent fallback do not obtain the
official file. Do not use impersonation to bypass access controls or to substitute
a non-official copy.

Inspect PDF text before relying on extraction. When the official PDF has a
defective text layer, retain the official PDF as the source snapshot and add a text
rendition or configured OCR path for extraction. Identify the rendition as derived,
record how it was produced, and compare headings, figures, signs, tables, and
operative wording against the rendered pages. A text rendition aids extraction; it
does not replace the official source or cure a missing adoption link.

Run the extractor only after the identification, operative-body, chronology, and
amendment checks have passed for the intended encode. Review inventory and
provision output against each document role before signing the scope.

## Signing and branch mechanics

Ingest-manifest signatures attest to a clean generator commit that must remain an
ancestor of the guarded head. Use this order:

1. Generate and review the corpus content.
2. Commit the content without the signed ingest manifest.
3. From the clean checkout, sign against `HEAD`.
4. Commit the signed manifest in a separate signing commit.

A rebase rewrites the attested content commit and breaks the recorded-ancestor
invariant. After signing, merge `main` into the branch instead of rebasing. If
history has already been rewritten, regenerate the manifest and re-sign against the
new clean `HEAD`; do not edit provenance fields by hand.

The same invariant governs how the pull request lands: merge with a true merge
commit only. A squash merge or rebase merge rewrites the attested branch
commit's ancestry and orphans the recorded commit exactly as an interactive
rebase does; this has required repair in practice after a squash merge.

Before handoff, run the scope's focused verification and the repository checks
required by `AGENTS.md`. Report the manifest path, document roles, identification
classification, operative body and date, year mapping, amendment sources, artifact
paths, and commands run. Publication remains a separate, explicitly authorized
operation.
