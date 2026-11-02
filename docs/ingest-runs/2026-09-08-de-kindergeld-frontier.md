# Kindergeld dependency capture tranche

This is a partial source-recovery tranche, not a published release or a
closure claim. The proposed successor preserves both scopes of
`de-rulespec-2026-07-21` byte-for-byte and adds twelve scopes with 935 rows.
The accompanying capture audit records every new provision body hash.

Captured with the existing `extract-de-gii` and `extract-official-documents`
commands, without adapter changes:

- AufenthG, FreizügG/EU and AO: complete current official juris XML acts,
  including all requested sections. Current capture does not establish
  historical applicability in 2025.
- KiZDAV: complete official juris XML.
- BGBl. 2026 I Nr. 156: complete official 24-page Altersvorsorgereformgesetz.
  Article 14(3) commences Article 3 on 1 January 2028.
- Regulations 883/2004 (31 July 2019), 987/2009 (1 January 2018), 859/2003
  and 1231/2010, plus the Withdrawal Agreement (OJ L 29, 31 January 2020).
  Cellar RDF work/expression/manifestation links resolve the German PDF
  items where EUR-Lex returns an empty HTTP 202 challenge.
- EEA Agreement: DVKA's original Official Journal excerpts, including
  Articles 1–2 and original signatories. This is not the 2025 party list:
  Switzerland appears among original signatories, and succession,
  enlargement and withdrawal require separate evidence.
- 22 DVKA bilateral agreements, protocols and implementing agreements for
  Bosnia and Herzegovina, Kosovo, Morocco, Montenegro, Serbia, Turkey and
  Tunisia. They remain undispositioned.
- Complete ARB 3/80, from its German Official Journal PDF item on page 60
  of OJ C 110 (25 April 1983), and EFTA's current contracting-party statement.
  The latter distinguishes the three EEA EFTA states from Switzerland;
  historical EU membership still requires period-specific evidence.
- Historical §270 SGB VI (1 January 2005–16 November 2016) and §217 SGB VII
  (1 July 2015–30 June 2020), from DRV's official versioned normative archive.
  Version-qualified citation paths avoid collision with the current
  repealed §270 row.
- RiStBV 2023, EStH 2024 §3 and AEAO 2025 §8. The two handbook pages were
  retained before BMF began returning CAPTCHA pages. Their retained source
  hashes are recorded in metadata; the other eight requested handbook
  pages remain uncaptured. Challenge pages are excluded from the selector.

International agreements use the existing `regulation` legal-instrument
container with `metadata.document_type: international agreement` (or
Association Council decision). Neither `treaty` nor `other` is accepted by
the corpus citation grammar. This container does not recharacterize the
instrument as a domestic ordinance; the subtype and authority are explicit.
No schema change is proposed.

BEEG §15 and SGB III §§24, 28 and 136 already have substantive rows in the
pinned July release and are reused. The captured SteFeG differentiates
the €3,336 child allowance for 2025 from €3,414 for 2026; the latter must
not be backdated merely because it appears in the current EStG row.

## Remaining work and publication gates

1. Recover EStH 2024 §§32, 32b, 33a; LStH 2023 §§3b, 8, 9; AEAO 2025 §9;
   and AO-Handbuch 2025 Anhang 45. Existing manifest lists the exact URLs.
2. Complete period-specific EEA membership evidence.
3. Complete discovery beyond the DA-KG citation seeds and the DVKA index;
   verify each case identity and BStBl II publication.
4. Obtain ingest signatures on the clean data commit through the authorized
   ingest signer. No ingest signing key is configured in this environment.
5. Review, merge by merge commit once signatures are present, then publish
   from corpus main. The selector is a cut plan; no release content SHA or
   publication receipt exists yet. Do not repin a consumer to the selector
   hash as if it were a signed release identity.

The original US encoding checkout and its uncommitted files were not edited.

## Validation

- GII and official-document focused tests: 150 passed.
- Ruff: passed; mypy: passed (92 source files).
- Every selected new scope reports zero missing and extra inventory rows.
- Full suite: 4,506 passed, 104 skipped, 208 deselected; four citation-grammar failures identified temporary unsupported classes and unlabelled HTML blocks. Those capture attempts were removed and regenerated through the existing extractor; the citation-grammar suite then passed all 19 tests.
- Release preflight must pass on the clean commit before promotion.
- This branch has no encoder modules, apply manifests or certification changes.
