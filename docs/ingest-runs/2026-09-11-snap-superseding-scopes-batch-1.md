# SNAP superseding scopes, batch 1: NC, GA, TN, OK, MI, KY (axiom-corpus#680 follow-on)

Date: 2026-09-11
Program: SNAP (`manifests/snap-completion-agent-queue.yaml`, 28 rows, six rows extended with
`superseding_scope`; `manifests/state-snap-manual-agent-queue.yaml`, 51 rows, the same six rows
extended with `superseding_scope` / `supporting_superseding_scope`)
Issue: https://github.com/TheAxiomFoundation/axiom-corpus/issues/680 follow-on; the revised editions
were recorded by `2026-09-10-snap-state-manual-completion-batch-{2,3}.md` and listed under "Revised
editions found during the SNAP completion pass" in `2026-09-11-program-ingestion-handoff.md`.
Agent: one session from a US network in the sparse worktree `~/axiom-corpus-worktrees/snap`, branch
`discovery/ingest-snap-superseding-1` cut from `origin/discovery/program-ingestion-union`, artifacts
written to the main checkout's `data/corpus` (`--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`).
Extractions started_at 2026-09-11T20:58:05Z (all six launched within 8 s of each other), Georgia
re-run 21:02:00Z to 21:02:22Z, release validations 21:02:05Z to 21:07:54Z; note committed at 2026-09-11T21:11:33Z. Per-state extraction
wall-clock seconds are in the table below (`date +%s` around each `extract-official-documents`).
Impact analysis: not run; the GitNexus MCP tools were not available in this session. No existing
function's behaviour changed: the only code change is additive in
`scripts/build_snap_state_manual_completion_manifests.py` (a `SUPERSEDING_SCOPES` overlay dict,
`SUPERSEDE_NOTE`, `RUN_NOTE_SUPERSEDE`, and one loop in `main()` that merges the overlay into the six
rows after the batch-3 static rows). Three manifest-pinning tests were re-pinned (below).

## What a superseding scope is (rule applied)

Released scopes are immutable and a release selector cannot carry one citation path twice, so a
revised edition of a document already in a released scope is taken as a whole-manual re-extraction
of the SAME manifest under a NEW version string, `2026-09-11-<state>-snap-manual-supersede`. Every
document-level citation path is identical to the released scope, so the next selector swaps the
released version for the superseding one. The manifests were edited in place: `source_url` where
the publisher serves the revision under a new file name (NC), and `source_as_of` / `expression_date`
for the revised documents; unchanged documents keep their released dates.

Date rule: `source_as_of` is the publisher's `Last-Modified` date of the file actually served (the
date the publisher revised the served object); `expression_date` is the revision or effective date
the document itself states (NC file-name dates, TN "Effective: June 1, 2026", GA MT 87 of June 1, 2026
and 3025's "Effective Date: June 15, 2026", MI bulletin effective dates, KY "R. 9/1/26"). Where the
document states no new date (OK Appendix D-4-C still reads 7/9/2025) `expression_date` is unchanged.
Georgia's HTML pages all carry `Last-Modified: 2026-09-01` (site regeneration), so for the MT 87 items
`source_as_of` is the transmittal date; for 3025 it is 2026-09-01.

Publisher policy: every fetch is the publisher's own URL over plain HTTPS with the extractor's
default request options (KY keeps the released `browser_user_agent: true`). No mirror, repost, proxy
or archive; TLS verification never disabled; `data/certs/` unchanged; no host blocked.

## Per-jurisdiction results

| Jurisdiction | Released scope | Superseding scope | Documents | Provisions (released -> new) | Revised documents confirmed changed | Extraction s |
| --- | --- | --- | ---: | --- | --- | ---: |
| us-nc | `us-nc/manual/2026-05-27-nc-fns-manuals-r2026-07-15-self-contained` | `us-nc/manual/2026-09-11-nc-snap-manual-supersede` | 79 | 723 -> 725 | 4 of 4 (FNS 212, 215, 340, 515) | 10 |
| us-ga | `us-ga/manual/2026-05-27-ga-snap-manual-r2026-07-15-self-contained` | `us-ga/manual/2026-09-11-ga-snap-manual-supersede` | 100 | 1,214 -> 1,207 | 18 of 18 MT 87 items, plus 3025 (new edition) and 3030 (cosmetic) | 24 + 22 (re-run) |
| us-tn | `us-tn/manual/2026-05-27-tn-snap-policies-r2026-07-15-self-contained` | `us-tn/manual/2026-09-11-tn-snap-manual-supersede` | 27 | 233 -> 233 | 1 of 1 (24.31) | 6 |
| us-ok | `us-ok/policy/2026-07-21-ok-snap-policy` | `us-ok/policy/2026-09-11-ok-snap-manual-supersede` | 10 | 113 -> 113 | D-4-C: new file, identical extracted text (see below) | 6 |
| us-mi | `us-mi/manual/2026-07-17-mi-bridges-manual` | `us-mi/manual/2026-09-11-mi-snap-manual-supersede` | 196 | 2,310 -> 2,317 | 20 of 20 (9 flagged in batch 3 plus 11 found by this pass) | 18 |
| us-ky | `us-ky/manual/2026-07-17-ky-snap-manual` | `us-ky/manual/2026-09-11-ky-snap-manual-supersede` | 2 | 400 -> 405 | 2 of 2 (Volumes II and IIA) | 5 |

Total: 414 documents, 4,800 provisions in six superseding scopes plus one 12-row Georgia companion
scope (below). Every scope reports `coverage_complete: true`, zero missing, extra or duplicate
citations. Disk before each extraction: 6.7 GiB to 7.0 GiB free (threshold 3 GiB); 5.1 GiB free at
the end (another session was writing `2026-09-11-{me,nd,nv,wy}-snap-manual-supersede` in parallel).

Verification per state (script in the session scratchpad, results reproduced in the tables below):
(1) coverage report complete; (2) per-document extracted text compared by SHA-256 of the
concatenated body hashes of the document row and its page/block rows in ordinal order, plus the
inventory source-file SHA-256 where the released inventory carries per-file hashes (OK, MI, KY; the
NC, GA and TN releases are self-contained objects with one synthesized hash); (3) body lengths:
no non-document row with an empty body in any new scope, no root-only document; totals 1,360,188
(NC), 1,520,537 (GA), 452,304 (TN), 396,892 (OK), 3,201,679 (MI), 684,448 (KY) characters;
(4) draft selectors validated (Controller section); (5) timing above.

### Citation-path sets

Document-level citation paths are identical to the released scopes in all six states (79, 100, 27,
10, 196, 2). Page and block sub-paths (`.../page-N`, `.../block-N`) are derived from the document's
page or block count, so they move where a revised edition changed length; nothing else moved:

- NC: FNS 340 shrank from 30 to 29 pages (`fns-340-deductions/page-29` gone); FNS 212 grew from 10
  to 13 pages (`page-10`, `page-11`, `page-12` new). TN, OK: sets identical.
- GA: 3025 collapsed from 24 to 10 blocks (`3025/block-11..24` gone: the new edition is a differently
  structured policy); 3205, 3335, 3405, 3515, 3614, 3715 and 3805 each gained one block.
- MI: BEM 106 lost `page-11`; BAM 220 gained `page-26..27`, BAM 401E `page-34`, BEM 500 `page-18..19`,
  BEM 503 `page-50..52`.
- KY: Volume II gained `page-347..349`, Volume IIA `page-53..54`.

These are recorded here explicitly as the instruction asked; they are not additions or removals of
documents. Whether an encoding cites a moved sub-path is a rules-repo check (`rulespec-us*` cites
document paths, e.g. `us-ga/manual/dfcs/snap/3614`, not block numbers, as far as this pass looked).


### NC revised documents (2026-05-27-nc-fns-manuals-r2026-07-15-self-contained -> 2026-09-11-nc-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-nc/manual/dhhs/fns/fns-212-household-composition-special-arrangements` | 10 -> 13 | 19,812 -> 24,889 | `ebb6328565099ac8` -> `01068e04008d684b` | `de139a894013d312` -> `bb003f8265e6cd5c` | 2026-08-31 / 2026-08-17 |
| `us-nc/manual/dhhs/fns/fns-215-residence` | 5 -> 5 | 7,749 -> 7,992 | `8e25db18992173d5` -> `f5dc7c447244dfa6` | `de139a894013d312` -> `6ed6a53976083963` | 2026-08-05 / 2026-08-04 |
| `us-nc/manual/dhhs/fns/fns-340-deductions` | 30 -> 29 | 55,954 -> 55,717 | `d33f011e48ffb6ee` -> `b0acc74800b5f767` | `de139a894013d312` -> `e16edcfb4294dcf4` | 2026-08-05 / 2026-08-04 |
| `us-nc/manual/dhhs/fns/fns-515-sr-changes-during-the-certification-period` | 13 -> 13 | 25,690 -> 29,721 | `d8206dab0de9e71f` -> `6ac26f0072255eff` | `de139a894013d312` -> `43aec1d058dab9f2` | 2026-08-14 / 2026-08-13 |

Other documents: 75 extract byte-identically to the released scope.
Citation-path set: documents identical (79 = 79); sub-paths gone 1 ['us-nc/manual/dhhs/fns/fns-340-deductions/page-29']; sub-paths new 3 ['us-nc/manual/dhhs/fns/fns-212-household-composition-special-arrangements/page-10', 'us-nc/manual/dhhs/fns/fns-212-household-composition-special-arrangements/page-11', 'us-nc/manual/dhhs/fns/fns-212-household-composition-special-arrangements/page-12']

### GA revised documents (2026-05-27-ga-snap-manual-r2026-07-15-self-contained -> 2026-09-11-ga-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-ga/manual/dfcs/snap/3025` | 25 -> 11 | 40,443 -> 44,618 | `556bbd94a43e7417` -> `b58bb09e89cb9114` | `baf221bef656061b` -> `05e4d4f15f278b5c` | 2026-09-01 / 2026-06-15 |
| `us-ga/manual/dfcs/snap/3030` | 13 -> 13 | 39,911 -> 39,909 | `1fc6bc0a989121da` -> `c46b2bcba4b7c3e1` | `baf221bef656061b` -> `4f5e522bffb58ed9` | 2026-05-27 / 2026-05-27 |
| `us-ga/manual/dfcs/snap/3035` | 23 -> 23 | 31,639 -> 33,264 | `db4d94b828586f59` -> `45d7db304b9eb708` | `baf221bef656061b` -> `1be4a78b5c167d00` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3105` | 32 -> 32 | 38,755 -> 38,684 | `128880b8fd4ce3c1` -> `0c827a267526d057` | `baf221bef656061b` -> `5a3fe643e96993e5` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3110` | 12 -> 12 | 10,201 -> 10,577 | `7d141b2249277697` -> `ae6d0367c00543c6` | `baf221bef656061b` -> `77b76641cbe6dae9` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3205` | 6 -> 7 | 11,332 -> 11,567 | `1358e1186f177337` -> `a10709685454fc3b` | `baf221bef656061b` -> `2ad218dc0917ef6d` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3335` | 5 -> 6 | 1,233 -> 2,212 | `0f43e38ebea804be` -> `4eb6b74d810f5ace` | `baf221bef656061b` -> `5252ec0e2267ef16` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3350` | 10 -> 10 | 16,430 -> 16,531 | `b142612c509b479c` -> `e9c83ce201b31b7d` | `baf221bef656061b` -> `11e487f4d8d80d84` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3405` | 25 -> 26 | 32,243 -> 33,122 | `0523dbfa81cc3186` -> `d0a31654fb97229f` | `baf221bef656061b` -> `2bc352c67bc6abf8` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3420` | 16 -> 16 | 39,081 -> 39,384 | `4d19276d8b60e934` -> `dde9186cb7dde87f` | `baf221bef656061b` -> `4e123253f548c273` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3515` | 7 -> 8 | 4,553 -> 4,932 | `076eba8e873a9a61` -> `0e46967166797657` | `baf221bef656061b` -> `b83862b6682f76bf` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3614` | 12 -> 13 | 20,908 -> 20,929 | `957fe920358a142f` -> `a1354833bfa7f613` | `baf221bef656061b` -> `f8a677b3783f8ab0` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3617` | 14 -> 14 | 14,892 -> 14,756 | `97d650f84fda3d55` -> `823a1c258e591b93` | `baf221bef656061b` -> `3641ffd98e9840bf` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3710` | 21 -> 21 | 17,305 -> 20,818 | `efc59985b059d53d` -> `5d77cea17181d9fb` | `baf221bef656061b` -> `d8999951c41ffd6a` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3715` | 24 -> 25 | 16,483 -> 16,662 | `432455e596a5ffda` -> `f760cd8bade2e8c1` | `baf221bef656061b` -> `f4d80dadaec0c162` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3725` | 13 -> 13 | 8,713 -> 9,245 | `64ebee67bd09e1a1` -> `951e21a98c5b14bd` | `baf221bef656061b` -> `83206f6cbc070269` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3730` | 13 -> 13 | 12,939 -> 13,566 | `3ac3301c06b564e6` -> `60bf4032bdc41319` | `baf221bef656061b` -> `f85f1a666cd6a55a` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/3805` | 18 -> 19 | 11,180 -> 11,707 | `db83416293e4f7c4` -> `428657b7ebc76f54` | `baf221bef656061b` -> `410bcf1b5b3045fe` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/appendix-e` | 3 -> 3 | 27,600 -> 28,050 | `54f9f5f7f46bc45a` -> `101b791ec8e080f3` | `baf221bef656061b` -> `4595428a3e318afd` | 2026-06-01 / 2026-06-01 |
| `us-ga/manual/dfcs/snap/appendix-f-forms-toc` | 3 -> 3 | 6,259 -> 6,256 | `e3618048db09d4e0` -> `a8a94676d59b540c` | `baf221bef656061b` -> `e37739a8e8e61b8a` | 2026-06-01 / 2026-06-01 |

Other documents: 80 extract byte-identically to the released scope.
Citation-path set: documents identical (100 = 100); sub-paths gone 14 ['us-ga/manual/dfcs/snap/3025/block-11', 'us-ga/manual/dfcs/snap/3025/block-12', 'us-ga/manual/dfcs/snap/3025/block-13', 'us-ga/manual/dfcs/snap/3025/block-14', 'us-ga/manual/dfcs/snap/3025/block-15', 'us-ga/manual/dfcs/snap/3025/block-16', 'us-ga/manual/dfcs/snap/3025/block-17', 'us-ga/manual/dfcs/snap/3025/block-18', 'us-ga/manual/dfcs/snap/3025/block-19', 'us-ga/manual/dfcs/snap/3025/block-20', 'us-ga/manual/dfcs/snap/3025/block-21', 'us-ga/manual/dfcs/snap/3025/block-22', 'us-ga/manual/dfcs/snap/3025/block-23', 'us-ga/manual/dfcs/snap/3025/block-24']; sub-paths new 7 ['us-ga/manual/dfcs/snap/3205/block-6', 'us-ga/manual/dfcs/snap/3335/block-5', 'us-ga/manual/dfcs/snap/3405/block-25', 'us-ga/manual/dfcs/snap/3515/block-7', 'us-ga/manual/dfcs/snap/3614/block-12', 'us-ga/manual/dfcs/snap/3715/block-24', 'us-ga/manual/dfcs/snap/3805/block-18']

### TN revised documents (2026-05-27-tn-snap-policies-r2026-07-15-self-contained -> 2026-09-11-tn-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-tn/manual/dhs/snap/24-31` | 5 -> 5 | 6,692 -> 6,935 | `83a450a1652c46d5` -> `e068523126255b95` | `e0e14bb679fc93a3` -> `5caee8d48e5193a6` | 2026-06-01 / 2026-06-01 |

Other documents: 26 extract byte-identically to the released scope.
Citation-path set: documents identical (27 = 27); sub-paths gone 0 []; sub-paths new 0 []

### OK revised documents (2026-07-21-ok-snap-policy -> 2026-09-11-ok-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-ok/policy/okdhs/snap/appendix-d-4-c` | 5 -> 5 | 4,595 -> 4,595 | `b3ae08282be033f4` -> `b3ae08282be033f4` (identical text) | `b2ad5bf13b05f68d` -> `090d386a39508c3b` | 2026-08-28 / 2025-07-09 |

Other documents: 9 extract byte-identically to the released scope.
Citation-path set: documents identical (10 = 10); sub-paths gone 0 []; sub-paths new 0 []

### MI revised documents (2026-07-17-mi-bridges-manual -> 2026-09-11-mi-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-mi/manual/mdhhs/bridges/bam/120` | 13 -> 13 | 19,616 -> 19,899 | `8edf3bcded99e044` -> `9103dbbd45003d3d` | `a11d513c0b5035cd` -> `d9a2a1a35b63049c` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bam/200` | 8 -> 8 | 12,769 -> 12,962 | `38e5870030545f51` -> `37d555abd55b90c5` | `a0cfec3a4864eb1e` -> `8a8170788283a650` | 2026-07-20 / 2026-03-01 |
| `us-mi/manual/mdhhs/bridges/bam/220` | 26 -> 28 | 41,432 -> 46,278 | `5fa9447ef2d1a438` -> `a9f4cc57849f2b9a` | `df931919653db83d` -> `eee5d400e3fdaf52` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bam/401e` | 34 -> 35 | 61,474 -> 61,793 | `c40d800ce12f6183` -> `3348c915bc141b10` | `15f1f75e661c2725` -> `e61c1549a7ab2777` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bam/toc` | 4 -> 4 | 2,618 -> 2,618 | `8ab4579611ed14cb` -> `cfa68421cbfddf84` | `19d8c766b66931b4` -> `5d1690f3b7a7cd66` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bem/106` | 12 -> 11 | 15,255 -> 14,858 | `7366c049bf0b6f24` -> `58a8260f8d0615a3` | `1cbb339b4c16aff7` -> `ba5818b98373d780` | 2026-08-17 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bem/171` | 5 -> 5 | 4,970 -> 4,854 | `3a2a5368a8ac4453` -> `297fb7006e56e867` | `ac5cec6164449dac` -> `500847cc709b6795` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/227` | 4 -> 4 | 2,969 -> 3,133 | `a761971fe8c08b14` -> `0522a514017221cf` | `e61acdc9bb1ad14a` -> `be6ffe70cfcfd129` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/230b` | 12 -> 12 | 17,631 -> 17,865 | `3ab9d6c6af386d42` -> `dbbaee4d2bb2dec6` | `3021b5c1cb886cb6` -> `e815ab4f4656433d` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bem/400` | 78 -> 78 | 111,933 -> 111,946 | `f4f49c3a1f8f0ece` -> `88f5b5f1d6b8e009` | `92bf297af52d2450` -> `ff379b6a7dbe656b` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/405` | 24 -> 24 | 33,857 -> 33,854 | `6a09e7ad9cb545ec` -> `697fa8c754e8cf36` | `8879d29861ebe45d` -> `9c99d0fd41cb3442` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/500` | 18 -> 20 | 25,631 -> 29,175 | `83c24dd60f4e91b1` -> `6011fe15c6c0cb91` | `b8bae0f59d2bc66f` -> `b846cc6d614433c4` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/503` | 50 -> 53 | 71,699 -> 73,177 | `ae9af6a4c8dbb7b3` -> `ccfe570362bf6eec` | `351665e90c5807b2` -> `79cb222f2577de77` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/550` | 8 -> 8 | 9,899 -> 9,995 | `38c4e0d2fecc618c` -> `e81ac31831bd72f1` | `f048db16e5b2c1cf` -> `61ed580d387d8817` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/554` | 38 -> 38 | 64,355 -> 60,840 | `72c3afb2fe699070` -> `37d41dfa13519a44` | `5366546cad16947b` -> `5b36a79845a4565b` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bem/617` | 10 -> 10 | 15,030 -> 14,971 | `353ff78ef45c7803` -> `042390acc79e4ae6` | `d0efcc1463179da4` -> `b0787334caafa893` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/630` | 13 -> 13 | 15,277 -> 15,625 | `0a43da156112ed4b` -> `9d22fb0be1acaf2c` | `dc7a1d2e56f1882e` -> `07d8a90a2d56ee0c` | 2026-08-03 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/bem/800` | 22 -> 22 | 29,128 -> 29,097 | `b8a5a64f5b4d9161` -> `9b9dca9ba86ead61` | `c05db865d8a1f0a8` -> `46141201d32a344a` | 2026-07-20 / 2026-04-01 |
| `us-mi/manual/mdhhs/bridges/bem/toc` | 7 -> 7 | 5,911 -> 5,912 | `acfec371cff08f21` -> `6e599b0c525fd4f6` | `a1ccfa2f2de47962` -> `85791e497fca1ebe` | 2026-08-17 / 2026-08-01 |
| `us-mi/manual/mdhhs/bridges/updates` | 20 -> 20 | 28,598 -> 28,944 | `3e18e553f4c1190a` -> `9783f78e984c0d87` | `daee9f2896b3b15f` -> `8576536e163ffa19` | 2026-08-17 / 2026-08-01 |

Other documents: 176 extract byte-identically to the released scope.
Citation-path set: documents identical (196 = 196); sub-paths gone 1 ['us-mi/manual/mdhhs/bridges/bem/106/page-11']; sub-paths new 8 ['us-mi/manual/mdhhs/bridges/bam/220/page-26', 'us-mi/manual/mdhhs/bridges/bam/220/page-27', 'us-mi/manual/mdhhs/bridges/bam/401e/page-34', 'us-mi/manual/mdhhs/bridges/bem/500/page-18', 'us-mi/manual/mdhhs/bridges/bem/500/page-19', 'us-mi/manual/mdhhs/bridges/bem/503/page-50', 'us-mi/manual/mdhhs/bridges/bem/503/page-51', 'us-mi/manual/mdhhs/bridges/bem/503/page-52']

### KY revised documents (2026-07-17-ky-snap-manual -> 2026-09-11-ky-snap-manual-supersede)

| Citation path | Rows | Chars | Extracted-text SHA-256 (released -> new) | Source file SHA-256 (released -> new) | source_as_of / expression_date (new) |
| --- | ---: | ---: | --- | --- | --- |
| `us-ky/manual/dcbs/dfs/volume-ii-snap` | 347 -> 350 | 595,475 -> 605,073 | `93ed837a2764fd35` -> `fa809357db9f0882` | `7ef887dacc2332da` -> `51400040476a0c09` | 2026-09-11 / 2026-09-01 |
| `us-ky/manual/dcbs/dfs/volume-iia-snap-work-requirements` | 53 -> 55 | 75,581 -> 79,375 | `efc49d19f5200b25` -> `4236caa48efc1c83` | `a1a7f8d111f38003` -> `cb5088b185b259d9` | 2026-09-09 / 2026-09-01 |

Other documents: 0 extract byte-identically to the released scope.
Citation-path set: documents identical (2 = 2); sub-paths gone 0 []; sub-paths new 5 ['us-ky/manual/dcbs/dfs/volume-ii-snap/page-347', 'us-ky/manual/dcbs/dfs/volume-ii-snap/page-348', 'us-ky/manual/dcbs/dfs/volume-ii-snap/page-349', 'us-ky/manual/dcbs/dfs/volume-iia-snap-work-requirements/page-53', 'us-ky/manual/dcbs/dfs/volume-iia-snap-work-requirements/page-54']

## Per-state findings

**us-nc** — The four August 2026 revisions are served under new file names on the index
(`FNS-212-Household-Composition-Special-Arrangements_8.17.2026.pdf`, `FNS-215-Residence_8.4.2026.pdf`,
`FNS-340-Deductions_8.4.2026.pdf`, `FNS-515-SR-Changes-during-Certification-Period_8.13.2026.pdf`;
Last-Modified 2026-08-31, 08-05, 08-05, 08-14) while the released URLs still serve the old files, so
the manifest's `source_url` for those four moved to the new files. A HEAD sweep of all 79 URLs
confirmed the other 75 are unmodified since the release (Last-Modified 2024-03-21 to 2026-02-05) and
their text extracts byte-identically.

**us-ga** — Every page on pamms.dhs.ga.gov answers `Last-Modified: 2026-09-01` (site regeneration),
so revision was judged on extracted text against the released scope: 20 of 100 documents differ. 18
are exactly the MT 87 items (dated 2026-06-01). Two are not on MT 87: 3025 "Americans with
Disabilities Act (ADA) and Section 504" is a new edition (the page now carries DFCS Civil Rights Policy
Manual policy 3601, "Effective Date: June 15, 2026", replacing FS Policy 3025 of December 4, 2020;
`expression_date` 2026-06-15, `source_as_of` 2026-09-01); 3030 differs by exactly two characters
(backticks removed around the policy number `3701` in its header; dates left as released). The four
Appendix A BOI table PDFs are unchanged (Last-Modified 2025-09-17; page rows identical). The index
still lists MT 85-87 only; no MT 88.

Cross-scope collision and companion scope: `validate-release` on the Georgia draft flagged
`duplicate_release_citation` for `us-ga/manual/dfcs/snap/3614/block-12`, which the released
`us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup` scope (13 rows) also carries: an orphan
(`parent_citation_path: null`) "Documentation Requirements" fragment from the July recovery fetch of
3614 that survived the July dedup because the May edition of 3614 had only 11 blocks. The superseding
scope now carries 3614's twelfth block in full (same heading, current text), so the fragment is
shadowed. Following the July `-r2026-07-17-dedup` and 2026-09-11 consolidation precedent, a 12-row
successor `us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup` was
built with `scripts/consolidate_release_scopes.py` from the single source
`2026-07-13-recovery-r2026-07-17-dedup` with `--include-citation-from` for its other 12 rows (8 Medicaid
2578 rows, 4 recovery release-scope rows); coverage complete, 12 = 12. The released scope is untouched;
the selector swaps both Georgia scopes.

**us-tn** — 24.31 Tennessee Summer Nutrition Initiative is the June 1, 2026 edition ("Date of Last
Review: 05/26/2026, Effective Date: 06/01/2026", Last-Modified 2026-06-01); the other 26 sections are
dated 2026-04-24 and extract byte-identically. Citation-path set identical.

**us-ok** — Appendix D-4-C's file is new (source SHA-256 `b2ad5bf13b05f68d` -> `090d386a39508c3b`,
Last-Modified 2026-08-28, PDF creation date 2026-04-18) but its four pages still read "7/9/2025" and
the extracted text is identical to the released edition, so this is a re-served file, not a text
revision: `source_as_of` 2026-08-28, `expression_date` kept at 2025-07-09. The C-3 landing page's raw
HTML again differs only in the site menu (extracted text identical); the C-3 allotment data, B-2, C-1,
C-3, C-3-A and the three OAC dependency API responses are identical. Citation-path set identical
(113 rows). The scope is therefore a like-for-like re-version; whether it is worth swapping is a
reviewer call (Controller section).

**us-mi** — A HEAD sweep of all 196 URLs found 20 files modified after the released 2026-07-17 fetch,
not the 9 batch 3 counted from the August bulletins. All 20 differ by SHA-256 and by text. Nine are
the August items (BEM 000, BEM 106, BEM 230B, BEM 554, BEM 630, BAM 000, BAM 220, BAM 401E, BPB log;
BPB 2026-019 to 2026-024, effective 8-1-2026). Eleven were re-served on 2026-07-20 as their BPB
2026-007 (4-1-2026) or, for BAM 200, BPB 2026-006 (3-1-2026) editions: BAM 120, BAM 200, BEM 171, 227,
400, 405, 500, 503, 550, 617 and 800; the released scope held older editions of each (for example
BEM 227 at BPB 2013-012 and BEM 171 at BPB 2017-001), so these are later editions the publisher
posted after the release even though their effective dates precede it. For all 20 the manifest's
`source_revision` (BPB number read from page 1), `source_sha256`, `source_as_of` (Last-Modified) and
`expression_date` (bulletin effective date) were updated; 176 documents extract byte-identically.
`contains_snap_policy` flags are unchanged (BEM 554 is now titled "SNAP Allowable Expenses and
Expense Budgeting").

**us-ky** — Both volumes moved again since the batch-2 probe. Volume II is OMTL-708 (table of contents
still "R. 8/1/26 OMTL-704", sections revised through R. 9/1/26; 349 pages; SHA-256
`51400040476a0c09`, Last-Modified 2026-09-11; released OMTL-701, 346 pages, `7ef887dacc2332da`; the
batch-2 probe saw `c9789d01...`). Volume IIA is OMTL-707, R. 9/1/26, 54 pages, `cb5088b185b259d9`,
Last-Modified 2026-09-09 (released OMTL-683, 52 pages, `a1a7f8d111f38003`). Metadata
`manual_revision_date`, `latest_omtl`, `source_last_modified` and `pdf_document_modified` updated. The
batch-2 completion scope `us-ky/manual/2026-09-10-snap-state-manual-completion` (Volume I) is a
different document and is untouched.

### Blocked publishers

None. Every host answered HTTP 200 to the plain extractor request.

## Commands run

```bash
# worktree
cd ~/axiom-corpus-worktrees/snap
git fetch origin && git checkout -b discovery/ingest-snap-superseding-1 origin/discovery/program-ingestion-union

# per state (df -h / checked before each; date +%s around the run)
uv run axiom-corpus-ingest extract-official-documents \
  --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --version 2026-09-11-<st>-snap-manual-supersede --manifest manifests/<manifest>.yaml
#   nc us-nc-fns-manuals | ga us-ga-snap-manual (run twice: the second after 3025's dates were set)
#   tn us-tn-snap-policies | ok us-ok-snap-policy | mi us-mi-bridges-manual | ky us-ky-snap-manual

# Georgia companion scope (drops the orphan 3614/block-12 fragment)
uv run python scripts/consolidate_release_scopes.py --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --jurisdiction us-ga --document-class manual \
  --source-version 2026-07-13-recovery-r2026-07-17-dedup \
  --target-version 2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup \
  --include-citation-from 2026-07-13-recovery-r2026-07-17-dedup=<each of the other 12 citation paths>

# draft selectors (scratchpad): the released selector with the version(s) swapped
uv run axiom-corpus-ingest validate-release --base /Users/pavelmakarchuk/axiom-corpus/data/corpus \
  --release <draft.json> --ignore-r2-missing --max-issues 50

# queues
uv run python scripts/build_snap_state_manual_completion_manifests.py --static-only
uv run ruff check scripts
uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"
```

## Artifacts (unsigned, uncommitted; `data/` is gitignored in the main checkout)

Under `/Users/pavelmakarchuk/axiom-corpus/data/corpus/{sources,inventory,provisions,coverage}/`:
`us-nc/manual/2026-09-11-nc-snap-manual-supersede` (725 rows, 12 MB of sources),
`us-ga/manual/2026-09-11-ga-snap-manual-supersede` (1,207 rows, 21 MB),
`us-ga/manual/2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup` (12 rows, 1.3 MB),
`us-tn/manual/2026-09-11-tn-snap-manual-supersede` (233 rows, 6.1 MB),
`us-ok/policy/2026-09-11-ok-snap-manual-supersede` (113 rows, 3.7 MB),
`us-mi/manual/2026-09-11-mi-snap-manual-supersede` (2,317 rows, 39 MB),
`us-ky/manual/2026-09-11-ky-snap-manual-supersede` (405 rows, 2.9 MB). Nothing under `data/corpus`
is committed. `data/certs/` unchanged.

Ruff: `uv run ruff check scripts` -> all checks passed (also on the three edited test files).

Tests: `uv run --extra dev pytest -q -m "not integration and not slow" -k "manifest or official_documents or discovery"`
in the worktree before the test edits -> 15 failed, 283 passed, 2 skipped. Twelve failures open
`data/corpus` artifacts the sparse worktree does not check out (the ten the gotchas note lists: BE
rulespec promotion, NY TANF compatibility x2, BE source promotion, AK/CT/MI-TOC/MT/ND/NY SNAP manual
tests; plus, on the union branch, `test_armenia_arlis::test_checked_in_tax_code_2024_continuity_sources_match_manifest`
and `test_israel_openlaw::test_pilot_manifest_pins_all_three_instruments`). Three were caused by this
pass and were re-pinned to the superseding editions:
`tests/test_us_ky_snap_manual.py::test_kentucky_snap_manifest_pins_both_current_official_manuals`
(per-document `source_as_of`, `expression_date`, `latest_omtl`),
`tests/test_us_ok_snap_policy.py::test_oklahoma_policy_manifest_uses_current_official_sources`
(D-4-C `source_as_of`), and
`tests/test_us_mi_snap_manual.py::test_michigan_manifest_pins_current_complete_bridges_manual`
(`EXPECTED_SOURCE_SET_SHA256` over the manifest's `source_sha256` set, per-date counts, expression-date
bound). The artifact-level tests in those files keep pinning the released artifact versions
(`VERSION` constants) until the superseding scopes are committed and signed. Final run after the
edits: 12 failed (exactly the twelve `data/corpus` failures above), 286 passed, 2 skipped, 4,528 deselected (48.96 s).

## Reviewer judgments (all of them)

1. Whole-manual re-extraction of the released manifest under a new version, never a partial scope;
   released scopes untouched; the selector swaps versions.
2. Date rule as stated above (`source_as_of` = served file's Last-Modified; `expression_date` = the
   document's stated revision or effective date; unchanged documents keep released dates).
3. Revision detection: HEAD sweeps of every manifest URL for Last-Modified and size (all six states),
   then extracted-text comparison of every document against the released scope; for GA the text
   comparison is the only usable signal (site-wide Last-Modified).
4. GA 3025 is a revision (new policy edition, effective June 15, 2026) and is dated accordingly even
   though MT 87 does not list it; GA 3030's two-character backtick cleanup is cosmetic and left undated.
5. GA 3614/block-12 collision resolved by a 12-row successor of the recovery-dedup scope, not by
   dropping the superseding row (the fragment was the stale July text; the superseding block is the
   current text) and not by folding the two scopes into one (keeps the superseding scope's citation
   set equal to the released manual's document set).
6. OK D-4-C: re-served file, identical text; scope built as instructed and left to the reviewer to
   decide whether to swap (no text changes; only `source_as_of` and the source bytes differ).
7. MI: the eleven 2026-07-20 re-served chapters are revised editions (later BPB numbers than the
   released files) and are taken; `contains_snap_policy` flags unchanged.
8. KY: taken as currently served (OMTL-708 / OMTL-707), superseding the batch-2 probe's OMTL-704 finding.
9. Sub-path moves (page/block counts) are recorded explicitly and not suppressed.
10. Tests: only the manifest-pinning assertions were re-pinned; artifact-version constants left at the
    released versions.
11. Queue rows: `superseding_scope` (+ `superseding_manifest`, `superseding_queue_status`,
    `superseding_companion_scope` for GA) added to the six completion-queue rows via the generator
    overlay; `superseding_scope` / `supporting_superseding_scope` (OK) added by hand to the six rows
    of the released 51-row SNAP manual queue; `queue_status` values unchanged.

## Controller section: selector swaps

The next successor selector (the `2026-09-11-us-rulespec-program-ingestion-union` draft, or the
released `us-rulespec-2026-08-23-canada-338-suspension-union` if cut separately) swaps:

| Jurisdiction / class | Drop (released) | Add (superseding) |
| --- | --- | --- |
| us-nc / manual | `2026-05-27-nc-fns-manuals-r2026-07-15-self-contained` | `2026-09-11-nc-snap-manual-supersede` |
| us-ga / manual | `2026-05-27-ga-snap-manual-r2026-07-15-self-contained` | `2026-09-11-ga-snap-manual-supersede` |
| us-ga / manual | `2026-07-13-recovery-r2026-07-17-dedup` | `2026-07-13-recovery-r2026-07-17-dedup-r2026-09-11-snap-supersede-dedup` |
| us-tn / manual | `2026-05-27-tn-snap-policies-r2026-07-15-self-contained` | `2026-09-11-tn-snap-manual-supersede` |
| us-ok / policy | `2026-07-21-ok-snap-policy` | `2026-09-11-ok-snap-manual-supersede` |
| us-mi / manual | `2026-07-17-mi-bridges-manual` | `2026-09-11-mi-snap-manual-supersede` |
| us-ky / manual | `2026-07-17-ky-snap-manual` | `2026-09-11-ky-snap-manual-supersede` |

The two Georgia swaps go together: swapping the manual alone re-creates the `3614/block-12`
duplicate. Validation of drafts built from the released selector with the swap(s) applied
(`validate-release --ignore-r2-missing --max-issues 50`): per-state drafts NC, TN, OK, MI, KY and GA
(both Georgia swaps) each `ok: true`, 0 errors, 541 warnings (the pre-existing `missing_parent_id`
warnings in `us-ca/regulation/2026-07-13-recovery`), 275 scopes, 24-32 s each; all six together
`ok: true`, 0 errors, 541 warnings; the 2026-09-11 union draft with all seven swaps `ok: true`, 0
errors, 546 warnings (541 + the 5 advisory `unsectioned_document_body` warnings), 536 scopes, 42 s.
The drafts live in the session scratchpad and are not tracked (CI validates every tracked selector
against the checked-in `data/corpus`).

Decisions for a human: (a) whether to swap Oklahoma at all, since the text is identical; (b) whether
moved page/block sub-paths matter to any encoding (checked only for document-level paths here);
(c) `signing`: the seven new scopes' artifacts (about 86 MB) join the sign-and-commit step of
`scripts/sign_release_scopes.sh` with the rest of the 2026-09-10/11 scopes.

## Remaining

Superseding scopes still needed from the completion pass: NE (Title 475 chapters 2 and 3), AR (manual and
appendices), NV (six chapters), WY (Table II), ND (landing/TOC/topics), ME (Ch. 609); a second session
was extracting ME, ND, NV and WY superseding scopes in parallel while this batch ran (artifacts
`2026-09-11-{me,nd,nv,wy}-snap-manual-supersede` seen on disk; not part of this note).
