# Wave 5 brief — SSI, LIHEAP and Medicare (group `ssi-liheap-medicare`)

Read `00-common-preamble.md` first. Worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/w5-ssi-liheap-medicare`,
branch `discovery/ingest-w5-ssi-liheap-medicare` (at main 9b0641afc). Inputs:
`wave5/ssi-liheap-medicare-extractable.csv` (442 rows: 357 are the 7 federal elements inherited by 51 states, 78 are
state-level) and `wave5/ssi-liheap-medicare-review.csv` (219 rows). Schemas `{ssi,liheap,medicare}-schema.yaml`; builder
`build_ssi_liheap_medicare_matrices.py` (note: its **state-level pointers are the 09-11 literals** — the 2026-09-13/14
LIHEAP benefit matrices, MSP income standards and SSI supplement standards scopes were never wired in; part of your Part B is
to check them). Queues: `manifests/{ssi,liheap,medicare}-agent-queue.yaml`.

## Part A targets

1. **Seven federal documents (each clears 51 cells; do these first, they are small):**
   - `SSI-F-CFR416-APPK`: 20 CFR part 416, Appendix to Subpart K (income excluded under other federal laws). The eCFR
     extractor skipped appendices in the 09-11 run ("adapter limitation, run note 2026-09-11"). Check `extract-ecfr`'s
     options for appendix nodes; if the adapter cannot, take the appendix page as an official document
     (`https://www.ecfr.gov/current/title-20/chapter-III/part-416/appendix-Appendix to Subpart K of Part 416`), version
     `2026-09-15-title-20-part-416-appendix-k`.
   - `SSI-F-POMS-SI-00529` (prisoners): one POMS subchapter, not in `2026-09-13-ssi-poms-si-remainder`. Same generator as
     that run (`scripts/build_ssi_poms_si_manifests.py`), version `2026-09-15-ssi-poms-si-00529`.
   - `LIHEAP-F-CFR96-96-80`, `-96-87`: the held part-96 scope has 96.81–86, 96.88, 96.89 but not 96.80 / 96.87. Check the
     eCFR structure: 96.80 may be reserved/withdrawn and 96.87 may be a heading-only section — if so record ABSENT with the
     eCFR structure evidence; otherwise extract them.
   - `LIHEAP-F-GUID-MODELPLAN`: the LIHEAP Model Plan (OMB form + instructions) from ACF OCS. Official-documents manifest,
     version `2026-09-15-liheap-model-plan`.
   - `MED-F-IOM-100-03` (NCD manual, 4 chapters) and `MED-F-IOM-100-05` (Secondary Payer, 8 chapters): same generator as
     `2026-09-13-medicare-cms-iom-100-16/-18` (`scripts/build_cms_iom_100_01_manifests.py` family), versions
     `2026-09-15-medicare-cms-iom-100-03` / `-100-05`.
2. **LIHEAP state manuals (`LIHEAP-ST-09` 37 states, `LIHEAP-ST-18` 35)**: the plan attachment / state policy manual the
   ACF Clearinghouse index links per state (`https://liheapch.acf.gov/stateplans.htm`, read live). Wave 4 took the
   benefit matrices (`2026-09-14-liheap-benefit-matrix`, 47 jurisdictions) — check each state's matrix scope first; a
   number of "policy manual" cells may be ALREADY-HELD there. Take the rest with the LIHEAP generator
   (`scripts/build_liheap_benefit_matrix_manifests.py` pattern), version `2026-09-15-liheap-policy-manual`.
3. **SSI state authority (`SSI-ST-2` OR UT VA WI; `SSI-ST-4`/`-5` OR)**: the adopted-rule family (e.g. OAR chapter 461
   OSIP on the Oregon SOS, HTTP 200). Version `2026-09-15-ssi-state-supplement-rules`.

## Part B — reading pass (219 cells)

- `LIHEAP-ST-05` (51 states) and `LIHEAP-ST-03` (30): read the cited plan sections.
- `MED-ST-7` (36 states, MSP income standards): **first** check `us-xx/*/2026-09-14-msp-income-standards*` (27
  jurisdictions, wave 4) — if the standard is there, record PRESENT with that citation (the builder never looked).
- `SSI-ST-2` (24) and `LIHEAP-ST-09` (13): read.
Cap ~250 cells.

## Part C

Run note `docs/ingest-runs/2026-09-15-ssi-liheap-medicare.md`, decisions
`docs/ingest-runs/2026-09-15-ssi-liheap-medicare-decisions.csv`, draft PR.
