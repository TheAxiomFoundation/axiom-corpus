# PR #551 Blind Adversarial Review Progress

## State

- Review worktree: `.git/review-worktrees/pr-551-f1176ed`
- Throwaway branch: `review/pr-551-f1176ed-blind`
- Independently resolved PR head: `f1176ed6641d31b09b1750eb1bc8eed84dd2159e`
- PR base reported by GitHub: `db12795577c5809009168982cf8a72fb58440620`
- Output file: `PR-551-REVIEW.md`
- Current phase: complete.
- Verdict: `REQUEST-CHANGES`.

## Done

- Read the repository instructions and GitNexus PR-review skill.
- Queried GitHub read-only for PR #551 metadata.
- Confirmed GitHub's head SHA matches the local branch and remote-tracking ref.
- Created this disposable worktree at the exact head without changing the PR branch or any remote.
- Recorded that direct `gh` access is sandbox-network-blocked while the read-only GitHub connector works.
- Indexed the pinned worktree locally with GitNexus; global registry registration was sandbox-blocked, so the local backend was queried directly.
- Mapped 14 target files (plus this review ledger): 67 indexed symbols, with no directly mapped execution-flow steps.
- Ran upstream impact analysis on every non-trivial changed production/reproduction symbol. `UscSection` is HIGH risk (47 symbols, 7 direct dependents); `_iter_sections` is HIGH risk (37 symbols, one direct caller, two recovery flows). New repro helpers are LOW risk.
- Confirmed the only production change preserves the optional official USLM section `status` attribute in normalized metadata.
- Independently counted official target structural nodes (section root inclusive): §27 1, §57 43, §58 17, §59 98, §901 131, §902 1, §903 1, §904 259; 551 section rows plus one title row.
- Verified the retained official ZIP hash (`d405deff…`), its sole XML member hash (`d2f67de8…`), and byte identity between the member and committed XML.
- Independently projected all 551 official source identifiers, headings, and bodies and found zero normalized mismatches or sequence differences; §§59 and 904 are complete through §59(l)(3) and §904(k).
- Explicitly tested the duplicate-numbered-sibling and mixed-part ordering regression classes: no duplicate identifiers, sibling collisions, mixed structural child ranks, hierarchy jumps, missing paths, extras, or ordering drift exist in this scope.
- Verified §902 is one blank-body section atom with `metadata.status = "repealed"`, no descendants, no amount, and no changed computation/rule implementation.
- Ran the signed manifest's literal portable command from a fresh worktree without a pre-existing virtual environment; it exited zero and regenerated all five applied artifacts with zero tracked drift.
- Verified all five manifest hashes, the Ed25519 signature, and that attested commit `c2f51414…` is an ancestor of the exact PR head.
- Confirmed two reproduction-command inconsistencies for final assessment: the committed run document and script's printed `REPRO_COMMAND` still retain the superseded `PYTHONPATH=src ... --no-cache --no-sync` command. That command exits one with `ModuleNotFoundError: pydantic` in the same clean environment.
- Compared concurrent PR #550 head `a942613c…`: the branches have one forced content conflict in `schema/citation-path.v1.json`. PR #551 records 6,710 live uppercase paths, PR #550 adds 82 disjoint paths, and the correct combined census is 6,792.
- Ran all requested gates: ruff, isolated-cache mypy, towncrier, citation validation, 78 release selectors, scoped tracking, coverage, and signed-ingest verification pass.
- Ran the full suite: 4,116 passed, 69 skipped, and 208 deselected; the sole PostgreSQL conversion failure reproduces identically on clean main.
- Audited normalization against neighboring main-branch Title 26 scopes, target-diff hygiene, the citation census delta, and the complete 14-file target scope.
- Wrote the evidence digest and verdict to `PR-551-REVIEW.md`.

## Next

- Author: replace the stale command in the run document and reproduction script, then rerun and re-attest/re-sign.
- Author: correct the claimed per-section counts to `1/43/17/98/131/1/1/259`.
- Integrator: resolve the PR #550/#551 citation census to 6,792 and revalidate after both scopes are combined.
