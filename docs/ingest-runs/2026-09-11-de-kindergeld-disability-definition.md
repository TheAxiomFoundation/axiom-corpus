# Disability definition and temporal boundary

This additive capture supplies the source definitions used in DA-KG A19.1 and
reviewed BFH disability judgments. It retains the current GII SGB IX and BTHG
consolidations (307 native rows) and DRV's dated 2001 and 2018 section 2 texts
(two roots and two complete normative rows). Coverage reports zero missing and
zero extra rows for both scopes. The new release selector preserves all 50
prior scopes and adds two: 52 scopes, 10,205 rows.

The dated 2018 section and current GII section are identical after whitespace
normalization. The 2001 text remains separately identified and valid through
31 December 2017 according to the official archive. All three paragraphs are
retained in each version. Severe disability and equal-treatment conditions are
not substitutes for the general disability definition. The full reviewed bodies,
hashes and temporal findings are in the adjacent audit JSON.

BTHG Article 26 is retained. Its current consolidation externalizes several
executed amendment articles, so this capture is not the complete original 2016
amending act. Current capture dates are not statutory commencement dates.
Neither corpus coverage nor these source reviews constitute legal encoding.

Reproduce from official endpoints with the native adapters:

```bash
PYTHONPATH=src axiom-corpus-ingest extract-de-gii --base data/corpus --version 2026-09-11-de-kindergeld-disability-definition --manifest manifests/de-kindergeld-disability-definition-gii.yaml --source-as-of 2026-09-11
PYTHONPATH=src axiom-corpus-ingest extract-official-documents --base data/corpus --version 2026-09-11-de-kindergeld-disability-definition-history --manifest manifests/de-kindergeld-disability-definition-history.yaml
```

Local DNS failed during acquisition. Downloads used publicly resolved addresses
while retaining the original HTTPS host and TLS certificate verification. The
GII replay loaded the declared laws with `load_german_gii_laws`, supplied each
unchanged downloaded archive as `GermanLaw.local_source`, and called
`extract_german_gii`. Historical HTML used the native official-document adapter's
`local_path` replay option. No adapter, legal body or generated row was edited.

Archive hashes: SGB IX
`1c76a914306814cd26abf1943476b804d767eaa3d2f23b81e8e67dc105b98ff9`;
BTHG `4a9d5953b33e3e756a00c927c0f7b7c45fd25c4f25e7c473ba624b49c64824ce`.
Historical HTML snapshot hashes are in the source manifest. Publication is
separate from serving activation. No certified claim.
