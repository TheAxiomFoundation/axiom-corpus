VERDICT: APPROVE

# PR #550 Blind Adversarial Review

No request-changes defect was found.

## Pinned review object

- GitHub reports PR #550 head
  `a942613cb190f09f191657aeb7199d31c8774f13` and base
  `db12795577c5809009168982cf8a72fb58440620`.
- The reported head matched both the local branch and
  `origin/ingest/usc-63-repair-165`.
- Review was performed in disposable worktree
  `.git/review-worktrees/pr-550-a942613` on throwaway branch
  `review/pr-550-a942613-blind`. No PR branch, remote, or GitHub write was
  made.
- GitNexus mapped the PR plus review ledger to 27 changed symbols, zero
  affected execution processes, and LOW risk. The new functional chain is
  confined to the standalone repro script and focused tests.

## Defect claim and §63 repair

The defect is real. On the pinned base, both actual §63 inventory entries use
the House §45A reader URL and resolve to a retained 177,385-byte XHTML blob
with SHA-256
`ce8b0ed86616c74c2b3926b516b5c42a8f7419157e4623ee9d05c392764c546e`.
The retained document self-identifies as `26 USC 45A: Indian employment
credit`, `documentid:26_45A`, and `Sec. 45A`; it contains neither `Taxable
income defined` nor §63's opening sentence. The official House §63 and §45A
granules independently identify those distinct sections.

The PR repairs exactly that provenance:

- All 62 §63 rows use the section-specific §63 reader URL.
- They cite the retained `usc26.xml` and its correct SHA-256
  `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621`.
- The 8,289,527-byte OLRC ZIP hashes to
  `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0`.
  Its sole member is `usc26.xml`, and that member is byte-identical to the
  committed 55,856,053-byte XML.
- Both source Git blobs are exact copies of already-retained base blobs. No
  retained source was reconstructed, reserialized, or hand-edited.
- The decoded §63 section body is byte-identical across both defective base
  copies and the repaired row: 8,119 bytes, SHA-256
  `7fa5f5d72de7ef69a3543175d7f57f83aaee5defb237144d85afef68564f153b`.
  The source's apparent §63(b)(6) drafting error and explanatory note remain
  unchanged.

## Reproduction

The manifest records a literal, parseable command with no angle-bracket prose:

```bash
uv run --extra dev python scripts/repro/us_63_repair_165.py --base data/corpus
```

The literal invocation was attempted and failed before Python started because
the sandbox denied `uv` access while initializing
`/Users/maxghenis/.cache/uv` (`Operation not permitted`). The required
source-only fallback used the exact worktree source with the repository's
existing environment:

```bash
PYTHONPATH=src \
  /Users/maxghenis/TheAxiomFoundation/axiom-corpus/.venv/bin/python \
  scripts/repro/us_63_repair_165.py --base data/corpus
```

It regenerated complete 163/163 coverage and left zero tracked drift. All five
regenerated hashes match both the committed artifacts and signed manifest:

| Artifact | SHA-256 |
| --- | --- |
| Coverage | `4f7fc692b9d572433bb88188b72f7377957a919fe7da05ed6a37081188480569` |
| Inventory | `4db559b49dc0b252eea3cf702b3d1f11a2be968da722de11bf87bc2985aadd81` |
| Provisions | `d7c41106a0e6456e14efafc98df1b907697d954d710e5890322b9db185160f79` |
| OLRC ZIP | `d405deff27cc0d05566100b852feff5f5a125fb81c6dd2896092f0262c9dbec0` |
| USLM XML | `d2f67de8052e9e2a96e3da34d84cbe2d677bc1b5840e8fa0e79cbfa7e9b28621` |

## Manifest integrity

- The signature is present, Ed25519, key ID
  `axiom-corpus-ingest-v1`, and decodes to 64 bytes.
- The repository-native `guard-ingested` command verified the signature with
  the configured Actions public key against the explicit PR base/head. It
  returned `passed: true`, no issues, and exactly the five protected files.
- Every `applied_files` hash matches the exact PR-head Git blob.
- Attested commit `de6927635ca61db0cb54277cadc4b1f95db77408` is an ancestor
  of the PR head; `git merge-base --is-ancestor` exited zero.

## §165 normalization and completeness

An independent ElementTree preorder walk of the ZIP-identical official USLM
found exactly 100 operative §165 nodes: one section plus 13 subsections, 35
paragraphs, 41 subparagraphs, and 10 clauses.

- Provision and inventory sequences equal official source preorder.
- All 100 citation paths, source identifiers, parent relationships, kinds, and
  independently extracted bodies match.
- There are no missing, extra, duplicate, or same-parent duplicate-numbered
  operative nodes.
- The 68 structural-looking elements without publisher identifiers are all
  inside editorial notes or quoted amendatory text and are correctly excluded.
- §165 contains no USLM `subpart`; all 41 formal subparagraphs are present.
- The Title 26 row has `body: null`, and the only normalized rows are the title,
  §63, and §165. The broad retained Title 26 archive is not passed off as a
  normalized atom.

The path/label/parent conventions match neighboring §§61–63 and §67. Legacy
main scopes for §§62 and 67 omit some deeper official descendants, so §165 is
more complete than those neighbors; that is pre-existing main incompleteness,
not a defect in this exact source-complete slice.

## Scope and hygiene

- The PR range has exactly 12 relevant files: five scoped corpus artifacts,
  signed ingest manifest, release selector, repro script, focused tests,
  ingest notes, changelog fragment, and citation-path ratchet.
- No `PROGRESS`, worker report, session, agent, or review artifact is in
  `origin/main..PR_HEAD`.
- The citation baseline change `uppercase_segments: 6327 -> 6409` is exactly
  explained by 82 new uppercase-bearing paths among the 161 new unique paths
  (61 §63 descendants and 100 §165 paths).

## Gates

| Gate | Result |
| --- | --- |
| Ruff | PASS |
| Towncrier | PASS |
| Citation-path grammar/census | PASS; 143,178 records, 124,651 unique paths |
| New-selector release validation | PASS; zero errors or warnings |
| Tracked-scope verification | PASS; five referenced files |
| Focused PR tests | PASS; 2 passed |
| Local full pytest | 4,115 passed, 69 skipped, 208 deselected; only the known PostgreSQL MagicMock conversion test failed |
| Pinned-base comparison of that test | Same failure |
| Local mypy | 180 inherited errors in 26 untouched files |
| Pinned-base mypy | Byte-identical output, SHA-256 `76c2b020c01bfbb5def2f4b1dd3871b4037fcd6d60c0cab76eca269647f71ce4` |
| Exact-head GitHub CI run `30327101788` | PASS, including artifact guard, changelog, ruff, clean Python 3.14 mypy, full pytest, citation grammar, all release selectors, workflow lint, and PostgreSQL |

Nothing fails on this head that passes on the pinned clean base.

## Sandbox disclosures

- The literal `uv` repro command was blocked by sandbox permissions on the
  home cache; the source-only replay passed byte-identically.
- Direct `curl` of the House source was blocked by sandbox DNS, and direct
  House page opens returned HTTP 403. Fidelity was therefore established by
  hashing and comparing the retained official OLRC ZIP, its sole XML member,
  the committed XML, pre-existing retained base blobs, and indexed official
  House granule/release metadata.
- GitNexus built a complete current worktree-local index but could not update
  its global registry outside the writable sandbox. The local graph was
  queried directly and the limitation did not block impact analysis.

Recommendation: approve. Preserve signed-manifest ancestry with a merge commit,
as required by the repository's corpus policy.
