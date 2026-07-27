# PR #506 Round-3 Re-review Progress

## State

- Review source is pinned to `660fff910529148f50866815447e37c1bf1044b7`.
- Work is isolated on local throwaway branch `codex/rereview-506-round3`.
- No PR-branch, remote, GitHub, publication, or production writes are allowed.
- Item 1(c) passes: all three derived Part 416 artifacts reproduce byte-for-byte.
- GitNexus maps the executable addition as LOW risk with no affected process.
- Round-3 review resumed from checkpoint `28cddc28` on 2026-07-27.
- The local GitNexus index is current at `28cddc28`; its global registry refresh
  was sandbox-blocked after the local index completed.
- History, manifest provenance, scoped selection, changelog, and formal-subpart
  parenting audits pass at pinned head `660fff91`.
- Exact upstream byte re-download is sandbox-blocked by DNS; retained source
  sizes and hashes match the runbook, and official browser-readable content
  corroborates the retained IRS document and Part 416 hierarchy.

## Done

- Confirmed the requested source commit exists locally.
- Created the isolated review worktree from that exact commit.
- Rebuilt a disposable GitNexus index and mapped the seven new script functions.
- Ran the Part 416 reproduction against a source-only temporary corpus base.
- Confirmed 622 full source rows, 14 selected rows, and complete coverage.
- Confirmed exact inventory, provisions, and coverage hashes and byte sizes.
- Confirmed the checkpoint ledger is committed and only two prior review JSON
  outputs remain untracked; neither will be committed.
- Confirmed four linear PR-only commits, no review artifacts, no current-main
  path overlap, and a clean three-way merge against `origin/main`.
- Confirmed both manifests attest ancestor `1568d98e`, record the literal
  committed invocations, and match all nine applied-file hashes.
- Verified both Ed25519 signatures locally with the public CI verification key;
  `guard-ingested` reports no issues.
- Confirmed issue #497's ten requested Part 416 sections plus Part/Subparts
  K/L/R are exactly the 14 retained rows, with no missing or extra paths.
- Confirmed all ten selected sections retain their formal Subpart K/L/R parent
  paths and UUIDs; the PR #523 formal-subpart flattening defect is absent.
- Confirmed the changelog fragment accurately describes the two new scopes.

## Next

- Run every requested local validation gate.
- Complete exact anchor/resolver and encoder-resolution adversarial checks.
- Write and copy the verdict report to the two required output paths.
