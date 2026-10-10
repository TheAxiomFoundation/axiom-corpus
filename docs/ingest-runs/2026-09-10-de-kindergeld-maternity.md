# Kindergeld maternity sources

DA-KG A 15.11 and A 17.2 depend on maternity employment prohibitions. The preceding DE release contained no MuSchG act or section rows. This additive cut captures the complete current MuSchG through the native GII adapter (46 rows), both official DRV versions of § 3 spanning 2025 (four rows), and the full official 2025 amending acts Nos. 59 and 371 (four rows).

The DRV archive expressly dates the earlier § 3 version from 1 January 2018 through 31 May 2025. Its successor begins on 1 June 2025 and adds the stillbirth sentence and miscarriage prohibition paragraph. The complete three-page Mutterschutzanpassungsgesetz confirms that transition in Articles 1 and 5. The two archived bodies match the entire selected official HTML after whitespace normalization, including every paragraph and numbered item. No historical text was reconstructed by editing the current act.

The current GII consolidation identifies the amendment in Article 13 of the Act of 22 December 2025, BGBl. I No. 371. That article adds MuSchG § 20(4), with commencement on 1 January 2026 under Article 14(1). The complete 52-page act is retained, but the legal review for this capture covered its MuSchG amendment and commencement provisions, not every other article. Other articles have different dates and may independently bear on benefits. The current act is not asserted to apply unchanged throughout 2025; historical application of sections other than the separately captured § 3 remains a source-bound review task.

Both PDF bodies match text extracted from every page of their official source PDFs after whitespace normalization. The companion audit records every nonempty body hash, retained source hash, selected-HTML check and PDF page count. All three native coverage reports are complete, with zero missing and zero extra rows. No adapter, generated provision body or prior release scope was edited.

## Reproduction and release boundary

Run `extract-de-gii` with `manifests/de-kindergeld-maternity-gii.yaml`, version `2026-09-10-de-kindergeld-maternity` and source-as-of `2026-09-10`. Run `extract-official-documents` with the corresponding `de-kindergeld-maternity-history.yaml` and `de-kindergeld-maternity-amendments.yaml` manifests and versions. The recorded final extraction replayed retained official bytes: GII through its supported `--source-dir`, and official documents through temporary manifests carrying supported `local_path` values and exact snapshot hashes. This changes transport only. The committed manifests retain the official URLs and avoid machine-local paths.

The named release preserves all 41 preceding scopes and adds three, for 44 scopes and 9,262 rows. Sign each scope from a clean reviewed data commit. Publication registers an immutable release; it does not activate serving, close Kindergeld dependencies, or authorize a certified claim.
