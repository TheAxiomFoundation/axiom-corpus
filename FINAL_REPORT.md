VERDICT: REQUEST-CHANGES

Target reviewed: `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`
(tree `91c0d556adcdb526cd52a1c9d5a077b424d3a5af`) in disposable
worktree
`/Users/maxghenis/TheAxiomFoundation/axiom-corpus/.git/review-worktrees/pr523-round4-1e0fde`.
No PR-branch, remote, GitHub, or publication write was made.

## Blocking finding

1. **MEDIUM — mixed retained eCFR parts still lose direct-section bodies.**
   `iter_ecfr_title_provisions` detects formal subparts, iterates only sections
   beneath those subparts, and then executes `continue` at
   `src/axiom_corpus/corpus/ecfr.py:1219`. Retained official 45 CFR part 1302
   contains direct §1302.1 followed by ten formal DIV6 subparts. The repaired
   hierarchy/inventory correctly contains
   `us/regulation/45/1302/1` beneath the part, but the provision iterator omits
   it. End-to-end extraction therefore manufactures a false placeholder with
   `body=null`, `structure_only=true`, and
   `body_status=not_in_ecfr_full_xml`, despite the official XML containing the
   section text; coverage misleadingly remains complete.

   Independent command:

   ```text
   PYTHONPATH="$PWD/src" /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python review-probes/ecfr_parentage_probe.py case data/corpus/sources/us/regulation/2026-06-24-title-45-part-1302/ecfr/title-45-part-1302.xml --title 45 --part 1302 --section 1302.1 --extract
   ```

   Source SHA-256:
   `1dc1b061cbb4b7ebb342b374ad58fdf6c66f118a39299b0e08b3bdb0e225e4b2`;
   result digest:
   `4cc7dc7c48519493bab1e9d75f46488c94843841b5ed5f54baa3f413da455de0`.
   An exhaustive independent scan of all seven retained canonical eCFR part
   XMLs found 3,501 unique section paths, 3,500 iterator paths, zero parent
   mismatches among emitted sections, and exactly this one missing path.
   Digest:
   `03abab761762002fcfc586a59a2d5210632ff8a89e7f0f46a727cd423d950ac1`.

   This behavior predates round 4, but the requested round-4 invariant was that
   hierarchy and provision-iterator parentage agree everywhere in the retained
   scopes. The eCFR repair is incomplete until direct sections are iterated
   alongside formal subparts and a real-body regression covers §1302.1.

## Round-3 defect disposition

- **USC collision loss: fixed.** The independent retained-OLRC probe reproduced
  58,347 outputs at `a64ec806`, missing exactly §45X(d)(4)(A),
  (A)(i), (A)(ii), and (B). At the target, pre-output traversal retained all
  58,368 structural occurrences; inventory and provisions each exactly matched
  the independently derived 58,351 unique official paths, in source order,
  with no missing or extra path. Official XML SHA-256:
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`.
- **Formal eCFR subpart flattening: fixed for the reported case.** On official
  §1302.10, `a64ec806` flattened the hierarchy to level 1 while the iterator
  referenced absent `subpart-A` at level 2. The target agrees on
  part → subpart A → §1302.10 at levels 0/1/2 and extracts a real body.
  Base digest:
  `33b86059cdeb54000dc547d74a5f1a6a5ffe6e3a7a38cbca632d71d9a781fdb0`;
  target digest:
  `dfac703cf86df44edb624ba1f186b424fe7a49c9d3e676f4558fcb10de39a413`.

## Adversarial results

- The USC target passed true immediate triplicates with unique IDs and with
  ID-less position fallback, same identifiers at different depths/parents,
  repeal→reenact sibling descendants, and cross-title isolation. Target matrix
  digest:
  `555d87d32acfead1f10e824a40ad9535fc9305400aeb63318e8adc8efe4022fc`;
  base digest:
  `2794d2911d394e8d375ebe32ee03324e9ba1f720e1134b72adbfdc79dc49ff96`.
- A same-parent duplicate XML `id` can still suppress a later unique branch,
  but that is invalid USLM input: retained official Title 26 has 82,680
  `id` occurrences and 82,680 unique values, and the
  [official USLM guide](https://xml.house.gov/schemas/uslm/1.0/USLM-User-Guide.pdf)
  defines the attribute as document-unique. No retained collision group is a
  repeal→reenact group. Citation-unique parent output remains intentionally
  first-wins while all unique descendants survive.
- The synthetic eCFR matrix confirmed consistent flattening of a non-DIV6
  `TYPE=SUBPART` variant, correct handling of a part without formal subparts,
  and exclusion of an unselected formal subpart and its section. Digest:
  `43b4dca61a6879debd519e536b2842ef285c8643771390b93abb9fd2e4c2461b`.
  No retained non-DIV6 formal-subpart variant exists.

## Reproduction, history, and scope invariants

- The a64→target delta is exactly the two requested linear repair commits,
  `7e1c8ab9b5efffa104841ce49fa42a30f63268b6` and
  `1e0fde9ba3bb3a9cfaa90c16bff02326d4b8667a`.
- The delta contains five files—two source modules, two tests, and one
  changelog fragment—not the prompt's literal “6 files.” Toolchain,
  workflows, and CODEOWNERS are untouched. No progress, scratchpad, or session
  path appears in the seven target-pinned PR-only commits.
- Both signed manifests record ancestor
  `afab29fc555af3d5bc25bba795e5b0c6ef936adc`; both
  `git merge-base --is-ancestor` checks exited 0. Manifest SHA-256 values are
  `4c5569fbf37660441db6f8d2cffbd6a061da36c547d088a66a3f7f97b006fbe2`
  (statute) and
  `56f7f5dc58046e9757e1b389f7dc1b69490b06a941fccdc6d57b6ae4f922796b`
  (regulation).
- The exact required `uv run --no-cache ...` wrapper could not start because
  sandboxed DNS blocked an `fsspec` download. Running the committed script with
  the target source and populated locked repository Python exited 0
  (statute 21/21 plus 18 anchors; regulation 2/2 plus 12 anchors). All eleven
  artifacts were byte-identical before/after; ordered hash digest:
  `5e8c0646ab2015987725991f188b08af954f2bc7134c0ccf30a5b8fa43403b02`.
  Exact individual hashes and command transcripts are in `PROGRESS.md`.

## Gate digest

- Ruff and Towncrier: pass.
- Citation validation: 142,992 records, 124,467 unique paths, all ratchets
  exact.
- Release validation: two scopes, zero issues.
- Tracked-scope checks: five statute files and four regulation files.
- Coverage: statute 21/21; regulation 2/2.
- Focused USC/eCFR tests: 56 passed.
- Resolver tests: 16 passed, 20 data-dependent skips; direct CLI anchor sweep:
  30/30 exact.
- Full pytest: 4,108 passed, 69 skipped, 208 deselected, and only the expected
  known PostgreSQL failure.
- Uncached configured CI mypy scope: zero errors in 89 files on both target and
  current `origin/main`. The historical 180-error full-mypy baseline was not
  reproducible in the available installed environments; recovered comparison
  diagnostics are recorded in `PROGRESS.md`.

## Tool and sandbox failures

- The first worktree command was invoked from the not-yet-created worktree and
  failed before execution; retry from the repository root succeeded.
- `npx gitnexus --help` hung during unavailable package/network resolution and
  was interrupted (130); a subreview's `npx --no-install gitnexus` likewise
  hung and was interrupted (130). Cached `gitnexus analyze` built the local
  index, but sandbox `EPERM` blocked global registry writing; it was interrupted
  after the usable local index was complete. Initial query batches omitted
  required repo selection and exited 1. Three private-helper impacts returned
  “target not found” from the older registered graph. Target-local backend
  queries then succeeded and are authoritative.
- Sandbox policy rejected attempts to use `apply_patch` outside the worktree.
  The subreview recovered with a permitted temporary-directory-local helper and
  later committed durable probes in this worktree. One `ps` diagnostic was
  sandbox-blocked. A one-second collaboration wait was rejected because the
  tool minimum is ten seconds.
- The required no-cache uv reproduction exited 1 on blocked PyPI DNS. Other
  exploratory uv probes likewise could not fetch missing packages, including
  `anthropic` and `pyparsing`. Fallbacks used the populated repository
  environment with target-first `PYTHONPATH`.
- One USC diff command used a guessed full SHA for `7e1c8ab9` and failed with
  an invalid revision range; `git rev-parse` resolved the exact commit and the
  rerun succeeded. A bare `python` shim pointed to a missing Homebrew binary
  (127), and the worktree-local `.venv/bin/python` was absent (127); stdlib
  probes used `/usr/bin/python3`, and adapter probes used the populated root
  repository environment. Two git diagnostics mistakenly ran in a temporary
  non-repository and exited 128, then succeeded from this review worktree.
- Initial Ruff checks of temporary review probes reported three auto-fixable
  import diagnostics. `ruff check --fix`, formatting, final Ruff checking, and
  bytecode compilation all succeeded before the durable probes were committed.
- Full pytest exited 1 solely for the explicitly expected PostgreSQL failure.
  Several non-gate mypy diagnostics exited 1: broader package/source scopes
  produced 2,201 or 128 errors; the system environment produced parity at 212
  missing-stub errors; and an incomplete temporary base archive produced 161.
  None supersedes the successful uncached configured CI scope.
- A diagnostic `jq paths` expression exited 5 from cross-input path reuse; a
  direct field query succeeded. A diagnostic shell glob for the GitNexus cache
  had no matches and exited 1; the installed module path was then resolved from
  the executable symlink. Deferred tool discovery returned no callable
  GitNexus MCP tool, so the cached standalone/local-backend route was used.

The committed `PROGRESS.md` is the command-level review ledger, and
`review-probes/usc_official_probe.py`,
`review-probes/usc_collision_matrix_probe.py`, and
`review-probes/ecfr_parentage_probe.py` are the durable independent probes.
