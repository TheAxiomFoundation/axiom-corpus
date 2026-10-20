# Wave 7 — common rules for every agent (read fully before starting)

Wave 7 closes what is left of the program-bundle gaps after wave 6 and the wave-5 remainder release
(`us-rulespec-2026-10-11-w5-remainder-union`): the documents the program bundles name that neither the served corpus,
that release, nor a wave-5/6 decision covers. The list comes from the axiom.org bundle collector run of
2026-10-12 17:20 UTC on the bundles of axiom-corpus#825 (see `../README.md`): 108 documents in 3 groups.
44 more rows (group `rejoin`) are already decided: the builder joined them to a served path, and they are
not yours.

Since axiom-corpus#825 the bundle generator joins a document to a manifest by its **full address, query included**.
A page served by one script for many documents (`GenerateRulePdf.do?fileName=…`, `page.aspx?item=…`,
`StatuteText?article=…&section=…`) is one document per query, no longer one per site.

## Where you work

- Your worktree and branch are named in your brief. It is a **sparse worktree** (`data/corpus/` excluded). Never symlink
  `data/corpus`; never `git sparse-checkout` anything else. Every extraction writes to the main checkout's corpus root:
  `--base data/corpus`. Artifacts there stay **uncommitted** (they are signed and
  committed later by the release step — not your job).
- Python: `uv run --extra dev ...` inside your worktree (a bare `pytest` resolves to the Anaconda one and fails
  collection). First command: `uv sync --extra dev` (one time, ~1 min).
- Read `CLAUDE.md` and `AGENTS.md` in the worktree root, `docs/agent-ingestion-runbook.md`, the wave-6 run note of your
  area (`docs/ingest-runs/2026-10-06-w6-<group>.md` on main) and the run notes your brief names, end to end, before
  extracting anything.
- Citation paths follow `docs/ingest-runs/2026-09-14-wave4-citation-path-slugs.md` (lowercase, stable,
  jurisdiction-prefixed, no spaces unless the jurisdiction's existing scopes use them).
- Version strings: `2026-10-12-w7-<family>` (never a bare date). Pass `--source-as-of 2026-10-12`. Never reuse or
  overwrite a version that exists under `data/corpus/provisions/<jur>/<class>/`.
- Disk: run `df -h /` before every batch. Stop extracting at 50 GB free and say so in the run note.
- Publisher access: official publishers only; the corpus user agent first; `browser_impersonation: chrome120` in the
  manifest only where a run note already documents that the publisher needs it
  (`docs/ingest-runs/2026-09-13-blocked-publishers-reprobe.md` lists them); TLS verification never disabled (add missing
  intermediates under `data/certs/` with `git add -f`). **No CAPTCHA, no mirrors, no reposts, no archived copies, no
  proxies.** A blocked publisher is an OUTREACH finding, recorded and moved past — do not work around it. One request at
  a time per host.
- Do not touch `manifests/releases/` or `manifests/program-bundles/`, do not sign (`sign_release_scopes.sh`,
  `sign-ingest-manifest`), do not cut or edit any selector, do not run `load-supabase` or anything that talks to Supabase
  or R2. Consolidation and the release cut happen after the agents finish.
- Do not edit another group's manifests. Prefer new manifests (`manifests/<jur>-<program>-w7-<family>.yaml`) and
  generator scripts over library changes. If you change a library function under `src/`, run the focused tests
  (`uv run --extra dev pytest -q -m "not integration and not slow" -k <module>`) and record "impact analysis: not run"
  in the run note.

## Inputs

`wave7/<group>.csv` (absolute path in your brief), one row per missing document, sorted by jurisdiction then action:

| column | meaning |
|---|---|
| `id` | the document's identity in the bundles: its corpus path, or else its web address |
| `jurisdiction` | `us` (federal layer) or `us-xx` |
| `programs`, `tiers` | the bundles that name it; `screener` = Tier 1 (PolicyEngine cites it) |
| `pe_cited_units` | how many provisions PolicyEngine cites in it (leverage) |
| `name` | the bundle's name for it |
| `bundle_url` | the address the bundle (PolicyEngine or a manifest) gives |
| `bundle_path` | a corpus path the bundle already assigns |
| `publisher_kind` | `official` (.gov/.us/state), `mirror` (Cornell LII, Justia, LegiScan …), `vendor` (Lexis …), `other` |
| `check_status`, `check_final_url` | one plain GET with the corpus user agent on 2026-10-12 (no retries) |
| `candidate_paths` | local corpus paths of the same jurisdiction whose last segment names an identifier in the address |
| `prior_decision` | a wave-6 decision that left it open (SKIPPED: not reached; ALREADY-HELD/PRESENT: held, yet still counted missing) |
| `action` | the starting point, below |

Actions:

- **MEASURE-CHECK** — a decision or a local scope says the corpus holds it, yet the bundle counts it missing. Find
  why: the bundle names an old path (record the served path; the join becomes a `path_moves` entry), the scope is not
  in the release (name it in the note), or the served tree lacks the document's root node (a container: say so). Record
  ALREADY-HELD with the served path when it is held; never re-extract held text.
- **REJOIN-CHECK** — `candidate_paths` lists corpus paths that may hold the document under another address. Open the
  address and the candidate's text (`data/corpus/provisions/...`): when one is the same document (same number and
  heading, an edition that is current law), record ALREADY-HELD with that path and `official_url` = `bundle_url`.
  Otherwise continue with the action its link check gives (FETCH, OFFICIAL-SOURCE, …).
- **FETCH** — the official publisher answered. Build the manifest entry with `source_url` **exactly** `bundle_url` when
  that is the address you fetched, query included (the bundle generator joins documents to manifests by the full
  address), extract.
- **CHECK-PUBLISHER** — a host that is not .gov. Decide whether it is the official publisher → FETCH; a third party →
  OFFICIAL-SOURCE if the law behind it has an official text, else OUT-OF-SCOPE.
- **OFFICIAL-SOURCE** — a mirror (Justia, Cornell LII, LegiScan). Find the official publisher's text of the same
  provision. Check whether a scope already holds it (ALREADY-HELD) before extracting.
- **DEAD-LINK** — 404, timeout or refused connection. Find the current official address of the same document and
  edition; else ABSENT.
- **BLOCKED-CHECK** — the publisher refused one plain request (401/403/429). Check the run notes for a documented
  fallback; else OUTREACH.
- **VENDOR** — an official code published only through a vendor (Lexis). OUTREACH unless the state hosts an official
  alternative.
- **PATH-ONLY** — a corpus path with no address (federal USC/CFR sections, whole titles or chapters). Extract with
  `extract-usc` / `extract-ecfr` into a `2026-10-12-w7-...-closure` version; for a whole title or chapter, check first
  whether a served scope holds its sections (then the gap is the container node: MEASURE-CHECK).

## Work, in order

1. **Held already?** For every row, first search the local corpus for it: `bundle_path` and `candidate_paths` in
   `data/corpus/provisions/<jur>/<class>/*.jsonl`, the document's heading, and `bundle_url` in the inventories
   (`data/corpus/inventory/<jur>/<class>/*.json`). When the text IS held, record ALREADY-HELD with `jur/class/version`
   and the citation path; do not re-extract.
2. Work the rest in this order: MEASURE-CHECK, REJOIN-CHECK, FETCH, CHECK-PUBLISHER, OFFICIAL-SOURCE, DEAD-LINK,
   BLOCKED-CHECK, VENDOR, PATH-ONLY. Within an action, higher `pe_cited_units` first.
3. Read every page you cite; never guess an address. Read the printed year/edition of every form or instruction you
   take.
4. Extract with the matching `uv run --extra dev axiom-corpus-ingest extract-*` command, check
   `data/corpus/coverage/...` (`complete: true`, no duplicates, no missing inventory entries), and record per-scope rows,
   chars and seconds.

## Outputs (all committed on your branch)

- `docs/ingest-runs/2026-10-12-w7-<group>.md` — the run note, same sections as the wave-6 notes.
- `docs/ingest-runs/2026-10-12-w7-<group>-decisions.csv` — **exactly one row per row of your group CSV**, columns
  `id,jurisdiction,programs,action,new_status,scope_version,citation_path,official_url,note`, where `new_status` is
  PRESENT, ALREADY-HELD, OUTREACH, ABSENT, OUT-OF-SCOPE or SKIPPED (meanings as in wave 6). `official_url` is the
  address you fetched (or found blocked); when it differs from `bundle_url`, the bundle is joined to your document
  through this row, so it must be right.
- Manifests, generator scripts, certs (if any) — committed. Nothing under `data/corpus/`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push the branch to
  `TheAxiomFoundation/axiom-corpus` (never a fork) and open a **draft** PR titled `Wave 7 <group>: …`, whose body
  summarizes the decisions by status and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  Never mark it ready and never merge.
- Final report (≤ 50 lines): rows by new status, scopes extracted (count, rows, MB), publishers blocked, what remains,
  the PR URL, disk free at the end.

Time-box: stop starting new extractions after about 3 hours of wall time; mark what is left SKIPPED and finish the
note, the decisions file and the PR with what you have. Commit and push as you go.
