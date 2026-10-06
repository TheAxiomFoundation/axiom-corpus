# Wave 6 — common rules for every agent (read fully before starting)

Wave 6 closes the program-bundle gaps: every document that the program bundles (axiom-corpus#780,
`manifests/program-bundles/<program>.yaml`: 13 programs, a federal layer and 51 state layers, two tiers) name and
the served corpus does not hold. The list comes from the axiom.org bundle collector run of 2026-10-06 (see
`../README.md`); 3,015 documents in nine groups, 2,694 of them cited by PolicyEngine (Tier 1, screener-level parity).
Nine agents run at the same time, one group each.

## Where you work

- Your worktree and branch are named in your brief. It is a **sparse worktree** (`data/corpus/` excluded). Never symlink
  `data/corpus`; never `git sparse-checkout` anything else. Every extraction writes to the main checkout's corpus root:
  `--base /Users/pavelmakarchuk/axiom-corpus/data/corpus`. Artifacts there stay **uncommitted** (they are signed and
  committed later by the release step — not your job).
- Python: `uv run --extra dev ...` inside your worktree (a bare `pytest` resolves to the Anaconda one and fails
  collection). First command: `uv sync --extra dev` (one time, ~1 min).
- Read `CLAUDE.md` and `AGENTS.md` in the worktree root, `docs/agent-ingestion-runbook.md`, and the run notes your brief
  names, end to end, before extracting anything. They show the manifest, generator-script, queue-row and run-note
  conventions you must follow. The wave-5 notes sit on their branches: `git show
  origin/discovery/ingest-w5-<group>:docs/ingest-runs/2026-09-15-<group>.md`.
- Citation paths follow `docs/ingest-runs/2026-09-14-wave4-citation-path-slugs.md` (lowercase, stable,
  jurisdiction-prefixed, no spaces unless the jurisdiction's existing scopes use them).
- Version strings: `2026-10-06-w6-<family>` (never a bare date; e.g. `2026-10-06-w6-income-tax-forms`,
  `2026-10-06-w6-tanf-manual`). Pass `--source-as-of 2026-10-06`. Never reuse or overwrite a version that exists under
  `data/corpus/provisions/<jur>/<class>/` (another agent may be writing a different version of the same class: always
  include `w6-` and your family in the version).
- Disk: run `df -h /` before every batch. Stop extracting at 50 GB free and say so in the run note.
- Publisher access: official publishers only; the corpus user agent first; `browser_impersonation: chrome120` in the
  manifest only where a run note already documents that the publisher needs it
  (`docs/ingest-runs/2026-09-13-blocked-publishers-reprobe.md` lists them); TLS verification never disabled (add missing
  intermediates under `data/certs/` with `git add -f`). **No CAPTCHA, no mirrors, no reposts, no archived copies, no
  proxies.** A blocked publisher is an OUTREACH finding, recorded and moved past — do not work around it. Other agents hit
  some of the same hosts (irs.gov, ssa.gov, state legislatures): one request at a time per host, no parallel fetching of
  one host.
- Do not touch `manifests/releases/` or `manifests/program-bundles/`, do not sign (`sign_release_scopes.sh`,
  `sign-ingest-manifest`), do not cut or edit any selector, do not run `load-supabase` or anything that talks to Supabase
  or R2. Consolidation and the release cut happen after all nine agents finish.
- Do not edit another group's manifests. Prefer new manifests (`manifests/<jur>-<program>-w6-<family>.yaml`) and generator
  scripts over library changes. If you change a library function under `src/`, run the focused tests
  (`uv run --extra dev pytest -q -m "not integration and not slow" -k <module>`) and record "impact analysis: not run"
  in the run note (the GitNexus MCP tools are not available).

## Inputs

`wave6/<group>.csv` (absolute path in your brief), one row per missing document, sorted by jurisdiction then action:

| column | meaning |
|---|---|
| `id` | the document's identity in the bundles: its corpus path, or else its web address |
| `jurisdiction` | `us` (federal layer) or `us-xx` |
| `programs`, `tiers` | the bundles that name it; `screener` = Tier 1 (PolicyEngine cites it) |
| `pe_cited_units` | how many provisions PolicyEngine cites in it (leverage) |
| `name` | the bundle's name for it |
| `bundle_url` | the address the bundle (PolicyEngine or a manifest) gives |
| `bundle_path` | a corpus path the bundle already assigns (a manifest names it, or a federal USC/CFR citation) |
| `publisher_kind` | `official` (.gov/.us/state), `mirror` (Cornell LII, Justia, public.law …), `vendor` (Lexis …), `other` |
| `check_status`, `check_final_url` | one plain GET with the corpus user agent on 2026-10-06 (no retries) |
| `manifest_on_main` | a manifest on main that already lists it (never extracted into a served scope) |
| `action` | the starting point, below |

Actions:

- **EXTRACT-MANIFEST** — a manifest on main names the document (`manifest_on_main`, mostly May 2026 tax-forms manifests
  from #56/#57) but no scope holds it. Check its edition against what the bundle wants (current law as of FY2027 /
  tax year 2025–2026); take it into a new wave-6 manifest (copy the entry, keep its `citation_path` unless the slug rules
  require a change, refresh `source_url` if the publisher moved it) and extract.
- **FETCH** — the official publisher answered. Build the manifest entry with `source_url` **exactly** `bundle_url` when
  that is the address you fetched (the bundle generator joins documents to manifests by URL), extract.
- **CHECK-PUBLISHER** — a host that is not .gov. Decide whether it is the official publisher (e.g. mainelegislature.org,
  oscn.net, a state agency's own .org/.com) → FETCH; a third party (taxsim.nber.org, an API endpoint, a Google Drive
  file, an advocacy site) → OFFICIAL-SOURCE if the law behind it has an official text, else OUT-OF-SCOPE.
- **OFFICIAL-SOURCE** — a mirror. Find the official publisher's text of the same provision (state legislature, register,
  agency). Check whether a scope already holds it (ALREADY-HELD) before extracting.
- **DEAD-LINK** — 404, timeout or refused connection. Find the current official address of the same document and
  edition; else ABSENT.
- **BLOCKED-CHECK** — the publisher refused one plain request (403). Check the run notes: some hosts have a documented
  `chrome120` fallback or an adapter on another official host (SSA POMS: `docs/ingest-runs/2026-09-10-ssi-poms-si.md`;
  California LegInfo: the `extract-state-statutes` adapter). Else OUTREACH.
- **VENDOR** — an official code published only through a vendor (Lexis). OUTREACH unless the state hosts an official
  alternative.
- **PATH-ONLY** — a corpus path with no address (federal USC/CFR sections missing from the selected scopes). Extract with
  `extract-usc` / `extract-ecfr` into a `2026-10-06-w6-...-closure` version.

## Work, in order

1. **Held already?** For every row, first search the local corpus for it: `bundle_path` (and its ancestors) in
   `data/corpus/provisions/<jur>/<class>/*.jsonl`, the document's heading, and `bundle_url` in the inventories
   (`data/corpus/inventory/<jur>/<class>/*.json`). The local root also holds unreleased wave-4/5 scopes. When the text IS
   held, record ALREADY-HELD with `jur/class/version` and the citation path; do not re-extract.
2. Work the rest in this order: EXTRACT-MANIFEST and FETCH, then CHECK-PUBLISHER, OFFICIAL-SOURCE, DEAD-LINK,
   BLOCKED-CHECK, VENDOR. Within an action, higher `pe_cited_units` first. Group documents of one publisher and class into
   one manifest and one scope where the conventions allow.
3. Read every page you cite; never guess an address. Read the printed year/edition of every form or instruction you take.
4. Extract with the matching `uv run --extra dev axiom-corpus-ingest extract-*` command (most rows:
   `extract-official-documents --manifest ...`), check `data/corpus/coverage/...` (`complete: true`, no duplicates, no
   missing inventory entries), and record per-scope rows, chars and seconds.
5. Update the program queue YAML rows (`manifests/<program>-agent-queue.yaml` or the family queue) the way waves 4–5 did,
   where your rows belong to a queue.

## Outputs (all committed on your branch)

- `docs/ingest-runs/2026-10-06-w6-<group>.md` — the run note, same sections as the wave-5 notes: work order,
  worktree/branch, publisher access (per publisher: what answered, what blocked), one section per family with method and
  a table of scopes (jurisdiction, version, rows, chars, seconds), what stays OUTREACH/ABSENT/SKIPPED and why, code
  changes, timing, disk.
- `docs/ingest-runs/2026-10-06-w6-<group>-decisions.csv` — **exactly one row per row of your group CSV**, columns
  `id,jurisdiction,programs,action,new_status,scope_version,citation_path,official_url,note`, where `new_status` is one of
  - `PRESENT` — you extracted it: `scope_version` = the new `jur/class/version`, `citation_path` = the document's root path;
  - `ALREADY-HELD` — a scope holds it: the scope and the path;
  - `OUTREACH` — the official publisher blocks the corpus client, or only a vendor publishes it;
  - `ABSENT` — no official copy exists any more (say what you searched);
  - `OUT-OF-SCOPE` — not a source of rules (a dataset, a calculator, an API, third-party analysis): say what it is;
  - `SKIPPED` — not reached in the time box.
  `official_url` is the address you fetched (or found blocked). When it differs from `bundle_url`, the bundle will be
  joined to your document through this row, so it must be right.
- Manifests, generator scripts, queue rows, certs (if any) — committed. Nothing under `data/corpus/`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push the branch to
  `TheAxiomFoundation/axiom-corpus` (never a fork) and open a **draft** PR titled `Wave 6 <group>: …`, whose body
  summarizes the decisions by status and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  Never mark it ready and never merge.
- Final report (≤ 50 lines): rows by new status, scopes extracted (count, rows, MB), publishers blocked, what remains,
  the PR URL, disk free at the end.

Time-box: stop starting new extractions after about 4 hours of wall time; mark what is left SKIPPED and finish the note,
the decisions file and the PR with what you have. Commit and push as you go (at least after each family), so nothing is
lost if the session ends early.
