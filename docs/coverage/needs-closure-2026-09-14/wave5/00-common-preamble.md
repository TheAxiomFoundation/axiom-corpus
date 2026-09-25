# Wave 5 — common rules for every agent (read fully before starting)

Wave 5 closes what the 2026-09-14 needs-closure recount (`docs/coverage/needs-closure-2026-09-14/README.md` on branch
`analysis/needs-closure-2026-09-14`, worktree `/Users/pavelmakarchuk/axiom-corpus-worktrees/closure-r6`) still marks
EXTRACTABLE, and turns the REVIEW column into decisions. SNAP and WIC crawling is exhausted (1% extractable); the bulk of
wave 5 is the tax, Medicaid, LIHEAP and CCDF families plus seven federal documents, and a reading pass.

## Where you work

- Your worktree and branch are named in your brief. It is a **sparse worktree** (`data/corpus/` excluded). Never symlink
  `data/corpus`; never `git sparse-checkout` anything else. Every extraction writes to the main checkout's corpus root:
  `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`. Artifacts there stay **uncommitted** (they are signed and
  committed later by the release step — not your job).
- Python: `uv run --extra dev ...` inside your worktree (a bare `pytest` resolves to the Anaconda one and fails collection).
  First command: `uv sync --extra dev` (one time, ~1 min).
- Read `CLAUDE.md` and `AGENTS.md` in the worktree root. Read one wave-4 run note end to end before extracting anything:
  `docs/ingest-runs/2026-09-14-state-tax-statute-ty2026.md` (statute + revenue-department documents) or
  `docs/ingest-runs/2026-09-14-tanf-whole-manuals-md-comar.md` (agency manuals) — they show the manifest, generator-script,
  queue-row and run-note conventions you must follow.
- Version strings: `2026-09-15-<program>-<family>` (never a bare date; e.g. `2026-09-15-liheap-policy-manual`,
  `2026-09-15-income-tax-forms-ty2025`). Pass `--source-as-of 2026-09-15`. Never reuse or overwrite a version that exists
  under `data/corpus/provisions/<jur>/<class>/`.
- Disk: run `df -h /` before every batch. **Stop extracting at 5 GB free** and say so in the run note. 26 GB free at launch,
  shared with four other agents.
- Publisher access: official publishers only; the corpus user agent first, `browser_impersonation: chrome120` in the
  manifest only where the run notes already document that the publisher needs it; TLS verification never disabled (add
  missing intermediates under `data/certs/` with `git add -f`, as wave 4 did). **No CAPTCHA, no mirrors, no reposts, no
  archived copies, no proxies.** A blocked publisher is an OUTREACH finding, recorded and moved past — do not work around it.
- Do not touch `manifests/releases/`, do not sign (`sign_release_scopes.sh`, `sign-ingest-manifest`), do not cut or edit any
  selector, do not run `load-supabase` or anything that talks to Supabase or R2. Consolidation and the release cut happen
  after all five agents finish.
- The GitNexus MCP tools are not available; if you change a library function under `src/`, run the focused tests
  (`uv run --extra dev pytest -q -m "not integration and not slow" -k <module>`) and record "impact analysis: not run" in
  the run note, as wave 4 did. Prefer manifests and generator scripts over library changes.

## Inputs

Your target lists (built from the recount matrices; absolute paths, read-only):

- `/Users/pavelmakarchuk/axiom-corpus-worktrees/closure-r6/docs/coverage/needs-closure-2026-09-14/wave5/<group>-extractable.csv`
  — one row per EXTRACTABLE cell: program, jurisdiction (`us` = federal element, inherited by all 51), element, level,
  family, note. The note names the publisher index or URL the 09-11/09-14 check found.
- `.../wave5/<group>-review.csv` — one row per state-level REVIEW cell: program, jurisdiction, element, family,
  scope_version, citation_path, note (why it is only a candidate).
- Element definitions: `.../needs-closure-2026-09-14/<program>-schema.yaml`; the matrices `<program>-matrix.csv`; the
  reports `<program>.md`.
- Provision rows to read: `/Users/pavelmakarchuk/axiom-corpus/data/corpus/provisions/<jurisdiction>/<document_class>/<version>.jsonl`
  (one JSON object per line: `citation_path`, `heading`, `body`, `kind`, `metadata`). The `scope_version` column is either
  the bare version (look up the class from the citation_path's second segment) or `jur/class/version`.

## Part A — ingestion (EXTRACTABLE cells)

1. Group your EXTRACTABLE rows by (jurisdiction, family). Federal rows (`jurisdiction == us`) come first: each is one
   document that clears 51 cells.
2. For each group, confirm the carrying document is actually not in the corpus: search the existing scopes of that
   jurisdiction and class for the citation paths or headings the element needs (`grep -l` over the JSONL, or a 10-line
   Python). A number of EXTRACTABLE cells are check-pattern misses, not gaps — when the text IS held, do not re-extract;
   record `already held: <scope>/<citation_path>` in your decisions file (Part C) instead.
3. Research the publisher index live (read every page you cite; no guessing at URLs), then build the manifest with the
   existing generator scripts where one covers the family (`scripts/build_*_manifests.py`; extend it rather than hand-writing
   manifests), extract with the matching `uv run axiom-corpus-ingest extract-*` command, and check `data/corpus/coverage/...`
   for the scope. Record per-scope rows, chars and seconds.
4. Update the program queue YAML rows (`manifests/<program>-agent-queue.yaml` or the family queue) the way wave 4 did.

## Part B — reading pass (REVIEW cells)

REVIEW means the check found a keyword hit that nobody read. Bound the work:

1. Sort your `<group>-review.csv` by element frequency. For each element with ≥ 5 REVIEW states, open the cited
   provision (`scope_version` + `citation_path`, body in the JSONL) for **up to 6 states**, read it, and decide whether the
   provision carries the element as defined in the schema.
2. If ≥ 5 of 6 carry it, the element's pattern is sound: record `PRESENT` for the six you read and `PATTERN-CONFIRMED`
   for the element (with the six citations) so the check can be tightened. If ≤ 1 of 6 carry it, record `ABSENT-IN-CITED`
   with what the text actually is, and say which family would carry the element (that is a new EXTRACTABLE or ABSENT
   finding). Mixed results: record each read cell individually and leave the element REVIEW.
3. Elements with < 5 REVIEW states: read them all (they are few).
4. Cap the pass at about 250 cells read per agent; report the cap and what was left.

## Part C — outputs (all committed on your branch)

- `docs/ingest-runs/2026-09-15-<group>.md` — the run note, same sections as the wave-4 notes: work order, worktree/branch,
  publisher access (per publisher, what answered and what blocked), one section per family with method and a table of
  scopes (jurisdiction, version, rows, chars, seconds), what stays EXTRACTABLE/ABSENT/OUTREACH and why, code changes,
  timing, disk.
- `docs/ingest-runs/2026-09-15-<group>-decisions.csv` — one row per cell you acted on:
  `program,jurisdiction,element,old_status,new_status,scope_version,citation_path,note` where new_status ∈
  PRESENT | ABSENT | EXTRACTABLE | OUTREACH | REVIEW | ALREADY-HELD | PATTERN-CONFIRMED | ABSENT-IN-CITED, and for
  newly extracted scopes the row cites the new `jur/class/version` and the citation_path that carries the element.
- Manifests, generator scripts, queue rows, certs (if any) — committed. Nothing under `data/corpus/`.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Push the branch to
  `TheAxiomFoundation/axiom-corpus` (never a fork) and open a **draft** PR whose body ends with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Final report (≤ 50 lines): cells closed by family, scopes extracted (count, rows, MB), publishers blocked, cells read
  and decisions by class, what remains, PR URL, disk free at the end.

Time-box: stop starting new families after ~4 hours of wall time; finish the note and PR with what you have.
