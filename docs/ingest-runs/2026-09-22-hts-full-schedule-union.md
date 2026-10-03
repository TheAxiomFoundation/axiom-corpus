# HTS full-schedule union: `us-rulespec-2026-09-22-hts-full-schedule-union`

Date: 2026-09-22
Branch `release/us-rulespec-2026-09-22-hts-full-schedule-union`, cut from `origin/main` at `942e138e`.
Predecessor selector: `us-rulespec-2026-09-14-wave4-r2-union` (1,042 scopes).

## Why

`us/statute/2026-08-09-usitc-hts-2026-rev15-full-schedule` (PR #595) normalizes all 29,845
HTS-numbered rows of the Revision 15 JSON export, plus the document root (29,846 rows). Its
retained source is byte-identical to USITC's published
`hts_2026_revision_15_json.json` (SHA-256 `59a76c12…`). No selector in `manifests/releases/`
carries it.

axiom.org's tariff schedule pages link each line's General and Column 2 rate citation to
`/us/statute/hts/<code>`. A rate line is a full-schedule row whose body has a
`Rates of duty (1-General):` or `Rates of duty (2):` line. There are 13,790 of them. The scope
that carries the predecessor's HTS lines has 975. The other 12,815 have no served provision
today, so they render the site's not-found page (for example `/us/statute/hts/0101.21.00`).

## Collision analysis

The predecessor's HTS lines come from
`us/statute/2026-08-09-rulespec-hts-current-with-legacy-aluminum-and-witnesses` (1,714 rows,
PR #596). The predecessor also selects `2026-08-04-usitc-hts-2026-rev15-notes`, whose
chapter 99 and General Note 3 pages sit under `us/statute/hts/`. Against the full schedule:

| | paths |
|---|---:|
| in both scopes, including the root `us/statute/hts` | 1,711 |
| in both, with a byte-identical `body` | 1,711 |
| only in the rulespec scope: 9903.85.02, 9903.85.08, 9903.85.12 | 3 |
| only in the full schedule | 28,135 |

On the shared paths:

- `kind`, `level` and `parent_citation_path` are identical.
- These fields differ on every path: `version`, `id`, `source_path`, `source_id`, `source_as_of`,
  `metadata` and `citation_label`. The full schedule keeps rates, units and footnotes in the body
  only, not in per-row metadata.
- `ordinal` and `parent_id` differ on 1,710 paths.
- `heading` differs on the root only; the full schedule's reads "... Revision 15 (full schedule)".
- `expression_date` and `source_url` differ on 2203.00.00, 2203.00.00.30, 8541.42.00 and
  8541.42.00.10. The rulespec scope took those four from the Revision 14 witness-lines scope
  (`2026-08-02-usitc-hts-2026-rev14-witness-lines`, expression date 2026-07-31). The full
  schedule carries the same text as Revision 15 (expression date 2026-08-03).

The three lines only the rulespec scope carries are 2025 Revision 16 Section 232 aluminum
lines, with expression date 2025-07-01. The Revision 15 schedule has no rows for them: its table
goes from 9903.82.26 to 9903.85.67. Its chapter 99 notes still refer to them (notes scope,
`chapter-99/page-184`, `-219`, `-221`, `-254`, `-255`).

The full schedule collides with no other scope of the predecessor. The notes scope's paths
(`us/statute/hts/chapter-99/...` and `us/statute/hts/general-note-3/...`) are disjoint from it.

## Design

`validate_release` (`max_issues=5000`) results for each candidate selector:

| candidate | errors | warnings |
|---|---:|---:|
| predecessor + full schedule | 1,711 `duplicate_release_citation` | 546 |
| predecessor − rulespec scope + full schedule | 0 | 546 |
| this selector (the row above + the legacy scope) | 0 | 546 |

The 546 warnings are identical in every candidate, and all of them are in scopes this cut does
not touch:

- 541 `missing_parent_id` in `us-ca/regulation/2026-07-13-recovery`;
- 5 `unsectioned_document_body` in the 2026-09-10 WIC and state-forms scopes.

The three HTS scopes of this selector validate together, with strict warnings, at 0 errors and
0 warnings. `tests/test_us_rulespec_2026_09_22_hts_full_schedule_union.py` pins that result.

- **Both HTS scopes cannot be selected.** A release with the `complete-expression-dates-v1`
  profile rejects any citation path carried by two of its scopes, whatever the bodies
  (`release_quality.py` `_release_citation_paths`, error `duplicate_release_citation`). The only
  exemption is the grandfathered `us-rulespec-2026-07-19` selector, pinned to its digest.
- **The full schedule wins every shared path, by selection.** Neither scope can be trimmed in
  place:
  - `publish_corpus.py` (`_require_safe_released_scope_reuse`) refuses to publish a scope that an
    activated release already carries if its artifacts differ. The rulespec scope is in the
    active `us-rulespec-2026-09-14-wave4-union`.
  - `scripts/deduplicate_release_selector.py` keeps a duplicated path in the scope listed by its
    `--canonical-selector` and strips it from the one added scope. It refuses this case, because
    stripping the 1,711 shared rows would orphan the rest of the full schedule.
  - `scripts/consolidate_release_scopes.py` needs an explicit carrier for any duplicate that is
    not an identical empty container.

  So the successor selector decides the winner. It keeps the full schedule because the full
  schedule:
  - carries every HTS-numbered line;
  - carries the four witness lines at Revision 15;
  - numbers its 29,845 lines 1 to 29,845 in schedule order, where the rulespec scope has
    sibling ordinal collisions.

  Serving it changes no body on any path the rulespec scope served.
- **The three legacy lines stay served.** rulespec-us `main` (`f43dec520`, 2026-09-22) cites them
  in these modules:
  - 9903.85.02 in `us/policies/usitc/us-tariff-duty/overlays/section-232-aluminum/general-rate.yaml`;
  - 9903.85.12 in `.../overlays/section-232-aluminum/uk-rate.yaml`;
  - 9903.85.08 in `us/policies/cbp/us-tariff-duty/composition.yaml` and the 100 generated
    tariff-schedule chapter compositions.

  They move to a three-row scope built from `2026-08-01-usitc-hts-2025-rev16`.
- **The legacy scope is self-contained.** The validator resolves a row's parent only within the
  row's own scope (`release_quality.py`, `missing_parent_citation`), and a second `us/statute/hts`
  root would duplicate the full schedule's. The legacy scope therefore detaches the parent link
  the way `scripts/self_contain_usc_scope.py` does for partial US Code scopes: it clears
  `parent_citation_path` and `parent_id`, and records `self_contained_root: true` and
  `detached_parent_citation_path: us/statute/hts` in metadata.

  The predecessor selector already carries 1,180 rows detached this way, across 9 scopes:
  - 1,029 California Revenue and Taxation Code sections;
  - 109 `us/statute` title 42 rows;
  - 42 title 26 rows.

  The active `wave4-union` serves the same 9 scopes. What this means for the three lines:
  - Citation-path resolution does not change.
  - Their navigation nodes are `us/statute` roots, sorted by their Revision 16 ordinals (1452,
    1458, 1461). They are not listed when browsing `us/statute/hts`.
  - On axiom.org, a parentless node's previous and next links run across all `us/statute` roots
    in sort-key order (`section-page.ts` `getNeighbor`). Its sibling strip lists every parentless
    row under `us/statute/hts/`, including the notes roots (`resolver.ts` `getSiblings`).

A first draft instead consolidated the full schedule and the three lines into one new scope
version. It was dropped for these reasons:

- it served the full-schedule rows under a new version name, while axiom.org's tariff data and
  the guard in axiom.org PR #261 key on `2026-08-09-usitc-hts-2026-rev15-full-schedule`;
- it re-versioned all 29,846 full-schedule rows, as about 83.5 MB of new provisions and
  inventory;
- it had to give the legacy lines an ordinal already used by a full-schedule row, because it
  kept every full-schedule ordinal;
- it listed 2025 Revision 16 lines under the Revision 15 root.

## Build

From the repository root:

```bash
uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union selector
uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union verify
uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union scope --base <corpus>
```

`scope` builds the legacy scope into a corpus base that holds the Revision 16 scope and the
full-schedule and replaced provisions. The base must not already contain the legacy scope:
`consolidate_release_scopes` refuses to overwrite one, so on a checkout of this branch run
`verify` instead. `scope` has three steps:

1. `consolidate_release_scopes` builds the scope from `2026-08-01-usitc-hts-2025-rev16`,
   restricted to the three legacy citations. The target is
   `2026-08-01-usitc-hts-2025-rev16-r2026-09-22-legacy-aluminum-self-contained`. Step 1 stages
   its output and writes nothing until its own checks pass.
2. `self_contain_scope` detaches the parent link.
3. `verify_scope` checks the result.

If step 2 or step 3 fails, `scope` deletes the four artifacts step 1 generated.

`verify_scope` derives the expected rows and inventory items from Revision 16 without calling
either tool. It then requires:

- the committed provisions, inventory and coverage to equal, byte for byte, what the build tools
  write for that derivation. That covers the versioned `id`, the cleared parent link, the detach
  metadata and the retained `source_path`.
- each legacy line to appear exactly once in Revision 16's provisions and inventory;
- the retained source tree to be byte-identical to Revision 16's, with no symlinks, and every
  inventory `sha256` to match its retained file;
- the full schedule to carry `us/statute/hts` and none of the legacy lines;
- every path of the replaced rulespec scope to resolve in the full schedule or the legacy scope,
  with the same body, kind, level and parent. Headings may differ only on the root. Dates and
  source URLs may differ only on the four witness lines. That exception is required: `verify`
  fails if any other path differs, or if one of the four does not.

The test file exercises the failure branches. `test_verify_scope_rejects_corruption` runs 14
corruptions, each of which must make `verify_scope` raise:

- the legacy rows' body, parent link, id, detach metadata and serialization;
- the inventory digest;
- a retained source byte, and a retained source replaced by a symlink;
- stale coverage;
- a shared full-schedule line dropped, and one changed in body, kind or date;
- the full schedule carrying a legacy line.

Result: 3 provisions, complete coverage (3/3). The retained source is the Revision 16 export
already in the repository (SHA-256 `69a3ddee…`, git blob `76be4b9d…`).

`selector` writes `manifests/releases/us-rulespec-2026-09-22-hts-full-schedule-union.json`:

- the predecessor's scopes, minus the rulespec HTS scope;
- plus the full schedule and the legacy scope;
- 1,043 scopes, sorted, with quality profile `complete-expression-dates-v1`.

The test file pins the selector and the rebuilt scope byte for byte. It also checks that every
`us/statute/hts` citation has one carrier in the release.

## Production boundary (not done in this branch)

1. **Sign the legacy scope's ingest manifest.** It has none yet. The full schedule's manifest was
   signed in PR #595. CI's `guard-ingested` rejects the legacy scope's four artifacts until the
   manifest exists. Signing needs the repository's ingest signing key
   (`AXIOM_CORPUS_INGEST_PRIVATE_KEY`, key id `axiom-corpus-ingest-v1`). From a clean checkout of
   this branch:

   ```bash
   : "${AXIOM_CORPUS_INGEST_PRIVATE_KEY:?missing ingest-manifest signing key}"
   uv run axiom-corpus-ingest sign-ingest-manifest \
     --jurisdiction us --document-class statute \
     --version 2026-08-01-usitc-hts-2025-rev16-r2026-09-22-legacy-aluminum-self-contained \
     --command 'uv run python -m scripts.repro.us_rulespec_2026_09_22_hts_full_schedule_union scope (run note: docs/ingest-runs/2026-09-22-hts-full-schedule-union.md)'
   git add .axiom/ingest-manifests/us/statute/2026-08-01-usitc-hts-2025-rev16-r2026-09-22-legacy-aluminum-self-contained.json
   git commit -m "Sign us-rulespec-2026-09-22-hts-full-schedule-union scopes"
   AXIOM_CORPUS_INGEST_PUBLIC_KEY=... uv run axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD
   ```

   `scripts/sign_release_scopes.sh` does not fit this flow, because it refuses once the selector
   already exists in `manifests/releases/`.

   Until the manifest is committed, CI's test job stops at the guard. Its later steps are skipped
   (install, towncrier, ruff, mypy, pytest), and so is the required `postgres` job, which needs
   `test`. The non-required `Validate named release selectors` job still runs.
2. **Merging publishes.** `.github/workflows/publish.yml` runs on every push to `main` that adds
   or changes a `manifests/releases/*.json` selector. Using repository secrets, it:
   - applies two release-staging database migrations;
   - validates the release;
   - uploads artifacts to R2;
   - stages provision and navigation rows in Supabase;
   - signs and registers the release object.

   It does not activate, and it does not read ingest manifests. For this release's scopes the
   only ingest-manifest gate is CI's `guard-ingested`, which runs independently of `publish.yml`.
   The publish job has no branch guard, so a `workflow_dispatch` of `publish.yml` on any ref
   publishes: do not dispatch it for this release before the PR merges. Branch protection's
   required checks do not bind admins (`enforce_admins` is false). So merge only after the
   manifest is signed and every check is green, including the non-required `Validate named
   release selectors`, and only when publication is intended.

   The repository allows merge commits only. That matters here: `guard-ingested` requires each
   manifest's recorded `axiom_corpus_git.commit`, the clean HEAD it was signed from, to be an
   ancestor of the guarded head.

   Push-triggered publication can fail and need a manual `workflow_dispatch` rerun with
   `release=us-rulespec-2026-09-22-hts-full-schedule-union`. For wave4-r2, push run
   34898524612 failed, dispatch 34906691454 failed, and dispatch 34909195701 succeeded after
   about 2 hours.
3. **Activation is separate, and it moves every pair this release carries.** Activation repoints
   each (jurisdiction, document_class) pair in the release object; this release carries 288.
   - On 2026-09-22, production served `us-rulespec-2026-09-14-wave4-union` on all 287 `us*`
     pairs (read from `corpus.active_scope_pointer`). `us-rulespec-2026-09-14-wave4-r2-union` was
     published but never activated.
   - So activating this release also ships wave4-r2's changes: the `us-al`, `us-de` and `us-ne`
     statute swaps from `2026-07-13-recovery` to the r2 chapter scopes, the `us-co` regulation r2
     scope, and the new `us-ct/regulation` pair.
   - The `release-activation` environment has no required reviewers. A dispatch of
     `activate-release.yml` with `request_activation=true` therefore activates as soon as its
     preview passes. Dispatch it first with `request_activation=false` and read the takeover
     list, then dispatch with `true` only when activation is intended.
   - The activate step can report failure after the activation has committed. wave4-union's
     activate step failed with a Cloudflare 524 at 21:48:59 UTC on 2026-09-14, while
     `corpus.active_scope_pointer` records the activation at 21:46:46. After a failure, read the
     pointer before retrying.

The full schedule's 29,846 rows are 2.4× the largest scope in any earlier selector (12,450
rows). The staged-evidence request splits work at the scope level only, so a gateway timeout on
this one scope would surface at publication.

## Follow-ups

- **axiom.org.**
  - PR #261 (branch `tariff-schedule-refresh`) adds tariff-page copy saying the rate text's scope
    "is not yet in a signed corpus release". That becomes false once `publish.yml` signs this
    release, which happens at merge, before activation.
  - The same PR's `assertScopeOutsideReleaseSelectors` greps selectors at the pinned
    `CORPUS_COMMIT` for the quoted version `"2026-08-09-usitc-hts-2026-rev15-full-schedule"`,
    which this selector contains. It will throw once the pin moves to a commit containing this
    selector, and the copy must be updated then.
  - After activation, check three pages:
    - `/us/statute/hts/0101.21.00`, which renders the not-found page today;
    - `/us/statute/hts/2203.00.00`, which cites the Revision 14 JSON today;
    - `/us/statute/hts/9903.85.08`.

    The first two should render the full-schedule row and cite its source URL, USITC's
    unversioned `hts.usitc.gov/reststop/exportList` endpoint. That endpoint served Revision 15
    when the scope was built; the retained bytes match the published Revision 15 JSON. The third
    should still render its Revision 16 row.
  - `getSiblings` fetches every child of a row's parent in one request. Under `us/statute/hts`,
    that is 29,845 rows.
- **rulespec-us.** `.axiom/toolchain.toml` pins `us-rulespec-2026-08-08-obbb-alien-snap`.
  - Re-pinning to this lineage is blocked by axiom-encode as well as by signing. The pinned ref
    `f856cfcb` refuses release objects over 16 MiB (`MAX_RELEASE_OBJECT_BYTES`). The
    predecessor's registered object is 21.2 MiB compact and 25.2 MiB pretty-printed with
    `indent=2`, which is the form the validation workflow writes. So the limit has to exceed
    about 25 MiB, and rulespec-us must also bump `axiom_encode_ref` in
    `.axiom/workflow-toolchain.toml` to the commit that raises it.
  - The full-schedule provisions file (45.7 MB) is 68% of the resolver's 64 MiB per-file limit.
  - A re-pin will likely change validation results for waived tariff modules that cite
    full-schedule-only paths, so those waivers will need review.
- **Next US union.** The wave-5 runs (#714-#718) are pending. Cut the next US union from this
  release, or re-apply its HTS swap. Activation repoints each pair to the activated release.
  Once this release is active, a later union that still selects the rulespec scope would put
  `(us, statute)` back on the rulespec rows. The same holds for the older open selector PR
  #627: it succeeds `us-rulespec-2026-08-23-canada-338-suspension-union` and still carries the
  rulespec scope.
