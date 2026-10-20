# Kansas LIEAP historical source intake, 2026-10-02

## Status and authority

This is the source prerequisite for
[rulespec-us#1469](https://github.com/TheAxiomFoundation/rulespec-us/issues/1469).
Extraction and signing are complete. This PR includes four signed ingest
manifests and four corpus locks covering all 33 artifacts. **Pavel completed
the object upload on October 20; release publication and a RuleSpec corpus-pin
update remain pending.** The October 2 audit remains a record of the original
unsigned extraction; the October 5 signing evidence and October 20 merge
validation are recorded below. This is not a published corpus release or
executable Kansas rules.

Official documents determine the rules. The tracking issue supplies discovery
leads and a review checklist; its proposed formulas, module paths, tests, and
PolicyEngine assumptions are not generation instructions. Later oracle
differences must be resolved against the official sources, not by changing an
encoding merely to match PolicyEngine.

[PolicyEngine/policyengine-us#9663](https://github.com/PolicyEngine/policyengine-us/pull/9663)
is the downstream comparison baseline, merged at
`a542eb99fa2aa520ad419ca3799a8b6d660f027d` on 2026-10-03 UTC (October 2 ET).
Its merge does not establish legal correctness or corpus admission. No
PolicyEngine package, YAML, or tests were used as ingestion input.

## Duplicate and release audit

The kickoff search found no Kansas LIEAP RuleSpec PR or historical-source PR.
Kansas SNAP PR rulespec-us#871 and corpus#718 cover different work.

The RuleSpec pin checked on October 2 is release
`us-rulespec-2026-08-08-obbb-alien-snap`, content SHA-256
`0d69a0cdbe024fc2276f3c261c00402bb0a47488ac5f482cc20bd3404980adbc`.
It includes the older `us-ks/manual/2026-05-27-ks-keesm-r2026-07-15-self-contained`
capture, but not the later Kansas LIHEAP plan/matrix scopes below. A manifest
being on corpus main does not put its contents into this pinned release.

Reuse these existing scopes; do not ingest them again:

| Existing scope | Source manifest | Verification this run |
| --- | --- | --- |
| `us-ks/policy/2026-09-10` | `manifests/us-ks-liheap-state-plan-fy2026.yaml` | All four locked files fetched and hash-verified |
| `us-ks/policy/2026-09-14-liheap-benefit-matrix` | `manifests/us-ks-liheap-benefit-matrix-attachments.yaml` | All four locked files fetched and hash-verified; first matrix page visually inspected |

## New captures

All 21 documents were independently downloaded from official publishers, then
downloaded again by `extract-official-documents`. Every extractor snapshot
matched the independently downloaded source SHA-256. The audit JSON next to this
note records each URL, source date, edition/date metadata, byte count, source
hash, citation path, and all 33 generated artifact hashes.

| Scope version | Jurisdiction/class | Documents | Corpus rows | Coverage |
| --- | --- | ---: | ---: | --- |
| `2026-10-02-ks-lieap-historical` | `us-ks/manual` | 17 | 34 | complete, no missing/extra/duplicate citations |
| `2026-10-02-ks-liheap-plan-fy2025` | `us-ks/policy` | 1 | 21 | complete, no missing/extra/duplicate citations |
| `2026-10-02-ks-liheap-matrix-fy2025` | `us-ks/policy` | 1 | 4 | complete, no missing/extra/duplicate citations |
| `2026-10-02-hhs-poverty-2024-2025` | `us/guidance` | 2 | 4 | complete, no missing/extra/duplicate citations |

Rows include document roots. Coverage here measures extraction against the
manifest's inventory; it does **not** certify complete Kansas policy coverage.

The manual captures sections 13000, 13200, 13300, 13360, 13400, 6300, 6313, and
7122 in the October 2024 and January 2026 editions, plus July 2025 section 13360.
Edition-specific citation paths (for example
`us-ks/manual/dcf/keesm/2024-10-01/keesm13360`) prevent collision with the existing
undated manual citations. Edition dates are not assertions that every provision
first took effect that day or remained unchanged throughout a fiscal year.
This is a selected historical dependency set, not a complete history of KEESM.

The FY2025 plan is the published **Revision 2**, with report status “Submission
Accepted by CO (Revision #2)” and report period October 1, 2024–September 30,
2025. The period start is not proof of when this revision took effect.

The HHS notices use GovInfo's article-specific HTML, which avoids ingesting
neighboring notices printed on the same PDF pages. Their publication dates and
stated applicable dates are separate metadata. They do not establish Kansas's
adoption dates or rounding rules.

## Reading checks and remaining policy questions

- Visually inspected all three FY2025 matrix pages: the first page identifies
  FY2025 and a 100.0% adjustment; electricity and propane continue across page
  boundaries. Page-level extraction preserves their text, not a typed benefit
  tensor. Reconstructing the table needs a separate source-grounded check.
- Visually inspected FY2025 plan page 9: section 2.6 gives estimated minimum
  and maximum heating benefits of $100 and $2,232. The retained PDF remains
  necessary for checkbox/radio-button selections; plain extracted text does
  not establish whether an option is checked.
- The existing FY2026 matrix's first page shows unadjusted and 80%-adjusted
  columns. Capturing that attachment does not prove which schedule DCF used
  operationally, nor justify applying a minimum to every matrix cell. Resolve
  adoption/minimum/supplement questions before shipping a benefit calculation.
- Verified the extracted October 2024 income table retains $1,882.50, $6,590.00,
  and the $672.50 additional-person amount. July 2025 and January 2026 retain
  $1,956, $6,769, and $688. Use the published tables; an inferred formula is a
  separate interpretation requiring review.
- The merged PE scope keeps regular-heating supplements in scope, with no
  FY2025/FY2026 operational supplement schedule established. The older issue
  body's exclusion of supplements should not silently become Axiom policy.
- Household facts, application-month income, deemed eligibility, and
  self-employment treatment must be derived from the dated sources. PE's
  annual-income and household proxies belong in oracle mappings/dispositions.

## Main merge and upload follow-up, 2026-10-20

[Pavel's review](https://github.com/TheAxiomFoundation/axiom-corpus/pull/778#issuecomment-6275900677)
confirmed byte-identical reproduction of all 33 artifacts and accepted the
19-block/3-page increase because it preserves the existing adapters' extraction
units. His [upload update](https://github.com/TheAxiomFoundation/axiom-corpus/pull/778#issuecomment-6299867174)
records 33 objects uploaded, zero failures, and zero remotely missing entries.
The previously failing jobs then passed on the original October 5 merge tree.
That rerun did not validate the subsequent merge from current main.

This branch merges `origin/main` at
`b5505bdbf0806c8d1469df3bbc37e4395d9cc0a4`, preserving signing ancestry.
All four corpus locks and all four signed manifests are byte-identical to
`a825f48a2`; the source artifacts require no re-signing or repeat upload.

The [full-tree main CI scan](https://github.com/TheAxiomFoundation/axiom-corpus/actions/runs/39478677536/job/118821229438)
fetched all 2,542 locked provision files and measured 764,665 records and
534,647 unique paths. Its live irregular counts exactly match main's ceilings.
A fresh local scan of this intake's 63 rows measures 19 `block_n` and three
`page_n` paths, with no other irregular family or identity drift. Main has
advanced beyond the earlier 88,143-block estimate in the review comment.

| Family | Measured main count / ceiling | Intake paths | Merged ceiling |
| --- | ---: | ---: | ---: |
| `block_n` | 105,398 | 19 | 105,417 |
| `page_n` | 178,885 | 3 | 178,888 |

All other ceilings and the empty identity-drift baseline remain exactly as on
main. The expected merged tree has 2,546 provision files, 764,728 records and
534,710 unique paths. These expectations must be checked by the full merged-tree
scan in PR CI; the scoped scan alone does not establish the union counts.

Local Ruff, mypy (103 source files), and Towncrier checks pass. Full local
pytest stops at the corpus-completeness guard: this checkout lacks 11,743
locked files from newer main scopes and has no R2 read credentials. No partial
test mode is used. The full merged-tree scan and test suite run in PR CI using
the existing read-only R2 credentials; their results are required before this
merge is considered validated.

The release successor should preserve the selected scopes of
`us-rulespec-2026-10-09-az-des-ece-dated` and add these four scopes plus the
existing FY2026 Kansas plan and matrix listed above. Publication is publish-only,
followed by a `rulespec-us` re-pin; this branch does not activate a release.

## Admission review, 2026-10-05 (historical evidence)

The user's reference-library copies of the FY2025 plan and benefit matrix
match the official-source SHA-256 values in the original audit. The FY2026
plan and matrix copies also match their existing corpus locks. The Drive
library supplies corroborating copies and source-discovery context; its
implementation notes do not replace official sources or resolve the policy
questions above. No duplicate FY2026 scope or Drive-only source was added.

Review verified all 33 local artifact hashes, re-downloaded all 21 official
sources with matching hashes, and reproduced all 42 content records from the
retained snapshots. The 63 rows include 21 document roots. All new citation
paths are unique and pass grammar and identity checks.

The full provision tree at PR head `2462155a92f7b95ca5464bc852097d5ddea49259`
contains 587,613 rows. Including the four new local scopes yields 587,676 rows
and 435,225 unique citation paths. Scanning this union reproduced exactly two
ratchet failures:

| Family | Previous ceiling | New paths | Union count / revised ceiling |
| --- | ---: | ---: | ---: |
| `block_n` | 75,916 | 19 | 75,935 |
| `page_n` | 150,654 | 3 | 150,657 |

The 19 blocks are the 17 dated KEESM HTML pages and two article-specific HHS
notices. The three page paths preserve the FY2025 matrix's PDF-page extraction.
These are the existing adapter's documented units for this intake, with raw
snapshots retained for layout and subsection interpretation. The schema change
allows exactly this measured increase. Other family ceilings and the empty
identity-drift baseline stay fixed. A full-corpus scan after admission remains
required; a scoped scan cannot verify these ceilings.

With every existing locked provision file materialized and the four new local
scopes present, `uv run --extra dev python scripts/validate_citation_paths.py`
passes for all 587,676 rows after this adjustment, with no grammar failures,
ratchet regressions, or new identity drift. Strict local deep validation of
the four scopes also passes with zero errors and zero warnings.

Follow-up checks after materializing all 56,318 existing locked artifacts:

- Full `uv run --extra dev python -m pytest -q`: **5,156 passed**, 104 skipped,
  208 deselected, 47 warnings. The repository's ingest public key was supplied
  for verification; partial-test mode was not used.
- Ruff, mypy (98 files), Towncrier against `origin/main`, and Git diff checks:
  passed.
- All four scopes pass the signer's lockability preflight.
- GitNexus reports documentation-section changes, zero affected execution
  flows, and low risk; the diff contains only schema, run-note, and changelog
  changes.

The earlier GitHub CI run for `2462155a` passed 5,153 tests, with 107 skipped,
208 deselected, and 90.17% coverage. It did not admit these new scopes: the
ingest guard saw no protected changes and remote verification checked zero
new lock entries.

All four extractions were repeated from clean tracked commit
`b5f170b65eeec17aaab592fd21f01bd7084dceb5`. All 33 generated artifacts remained
byte-identical to the original audit. The existing local ingest signing key
was verified against the repository's configured ingest public key, then used
to sign all four scopes with this generator commit. Each scope now has a signed
manifest under `.axiom/ingest-manifests/` and a matching lock under
`.axiom/corpus-locks/`. No replacement key or trust-root change was needed.
R2 upload credentials have not yet been located; no object upload is claimed.

## Reproduce extraction

The recorded extraction ran from clean tracked commit
`f09dc1099` (the full commit is in the audit JSON). No corpus rows were edited
by hand. Run from a clean committed checkout; keep generated corpus bytes out
of Git.

```bash
uv sync --extra dev --locked
mkdir -p tmp/ks-source-audit
uv run python - <<'PY'
from pathlib import Path
import certifi
Path('tmp/ks-source-audit/ca.pem').write_bytes(
    Path(certifi.where()).read_bytes()
    + Path('data/certs/entrust-dv-tls-issuing-rsa-ca-2.pem').read_bytes()
)
PY
export REQUESTS_CA_BUNDLE="$PWD/tmp/ks-source-audit/ca.pem"
uv run python - <<'PY'
from pathlib import Path
import subprocess
import yaml
for name in (
    'us-ks-keesm-lieap-historical',
    'us-ks-liheap-state-plan-fy2025',
    'us-ks-liheap-benefit-matrix-fy2025',
    'us-hhs-poverty-guidelines-2024-2025',
):
    manifest = Path('manifests', name + '.yaml')
    version = yaml.safe_load(manifest.read_text())['version']
    subprocess.run([
        'uv', 'run', 'axiom-corpus-ingest', 'extract-official-documents',
        '--base', 'data/corpus', '--version', version,
        '--manifest', str(manifest),
    ], check=True)
PY
```

TLS verification remains enabled. The added Entrust intermediate handles the
ACF host's incomplete certificate chain; it is not an insecure-download flag.
The extractor emits an HTML-parser warning for DCF's XHTML-style declarations;
the retained bodies and year-specific table checks passed.

Before signing, compare every captured source against this audit:

```bash
uv run python - <<'PY'
from pathlib import Path
import hashlib
import json
audit = json.loads(Path(
    'docs/ingest-runs/2026-10-02-ks-lieap-historical-audit.json'
).read_text())
for source in audit['sources']:
    actual = hashlib.sha256(Path(source['path']).read_bytes()).hexdigest()
    if actual != source['sha256']:
        raise SystemExit('Source changed; review required: ' + source['url'])
print('All 21 source hashes match the reviewed capture.')
PY
```

If a publisher changed a file, review the new version and append a new audit;
do not silently update hashes to make the comparison pass. Generated artifact
hashes are also recorded for comparison with the original run; a rerun must
have its own honest generator provenance.

## Signing reproduction and remaining upload

The signing step below is recorded for reproduction. It has already completed
for all four scopes using `--lock`; `--push` still requires object-upload access.
Use a clean tracked checkout and verify the audit hashes before re-signing:

```bash
uv run python - <<'PY'
from pathlib import Path
import shlex
import subprocess
import yaml
for name in (
    'us-ks-keesm-lieap-historical',
    'us-ks-liheap-state-plan-fy2025',
    'us-ks-liheap-benefit-matrix-fy2025',
    'us-hhs-poverty-guidelines-2024-2025',
):
    path = Path('manifests', name + '.yaml')
    manifest = yaml.safe_load(path.read_text())
    source = manifest['documents'][0]
    command = shlex.join([
        'uv', 'run', 'axiom-corpus-ingest', 'extract-official-documents',
        '--base', 'data/corpus', '--version', manifest['version'],
        '--manifest', str(path),
    ])
    subprocess.run([
        'uv', 'run', 'axiom-corpus-ingest', 'sign-ingest-manifest',
        '--base', 'data/corpus', '--jurisdiction', source['jurisdiction'],
        '--document-class', source['document_class'],
        '--version', manifest['version'], '--command', command,
        '--lock', '--push',
    ], check=True)
PY
```

The remaining upload can use the existing signed manifests and locks:

```bash
uv run axiom-corpus-ingest corpus push \
  us-ks/manual/2026-10-02-ks-lieap-historical \
  us-ks/policy/2026-10-02-ks-liheap-plan-fy2025 \
  us-ks/policy/2026-10-02-ks-liheap-matrix-fy2025 \
  us/guidance/2026-10-02-hhs-poverty-2024-2025
uv run axiom-corpus-ingest corpus verify --remote --changed-since origin/main
uv run axiom-corpus-ingest guard-ingested --base-ref origin/main --head-ref HEAD
```

Keep raw corpus bytes out of Git. Keep this PR in draft until uploaded objects
are present and the ingest guard and CI pass. Corpus merges must preserve
history: **no squash or rebase merge**.

After ingestion, a separately approved immutable release and RuleSpec pin
update must include the new scopes and existing FY2026 plan/matrix. Publication
or activation is not authorized or performed by this source-preparation PR.
Then generate from the admitted legal citations with personal Codex; use exact
reviewed-commit promotion for eligible rule/test files, followed by protected
validation/signing approval. Do not mark that end-to-end experiment complete
until its CI and unchanged-byte evidence exist.

## Original extraction validation, 2026-10-02

- Four live official-document extractions: 21 documents, 63 rows; complete
  structural coverage, zero missing/extra/duplicate citations.
- All 21 snapshot SHA-256 values match independent official downloads; all
  33 artifact hashes recorded; citation paths unique across the new scopes.
- Year-specific manual income-table checks and PDF visual checks above passed.
- `AXIOM_CORPUS_PARTIAL_TESTS=1 uv run --extra dev python -m pytest -q tests/test_corpus_documents.py`:
  **104 passed**, 5 existing PyMuPDF/SWIG deprecation warnings.
- `uv run --extra dev ruff check .`: passed.
- `uv run --extra dev towncrier check --compare-with origin/main`: passed
  with the source-preparation changelog fragment.
- `uv run --extra dev mypy src/axiom_corpus/corpus --ignore-missing-imports`:
  passed, 97 files.
- Full `uv run --extra dev python -m pytest -q`: **not run to completion**;
  session setup exited because 55,261 unrelated locked artifacts were not
  fetched. The focused run uses the repository's explicit partial-test mode;
  it is not represented as a full-suite pass. GitHub CI fetches the full tree.
- GitNexus `detect-changes --scope staged` found no indexed code-symbol changes;
  manual Git diff review confirms manifests/docs/changelog only.
