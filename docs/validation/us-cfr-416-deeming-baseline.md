# Deeming reproduction baseline provenance

[The manifest](us-cfr-416-deeming-baseline.json) records a compatibility replay
from producer commit `f22e9a458aa23ce8d0d28f05c58d2fe25360c8fc`, verified with its
unchanged `uv.lock` on 2026-09-06. The replay produces 622 source paths and the
approved 14-record slice with complete coverage. Its provisions SHA-256 is
`94b7ada5c604b276813b0854b67a15d869baae6e846159730801b412b7f4daa6`.

The checked-in July provisions file has SHA-256
`b7cbb4a14b218bcbcafa498ac97f4bd912004258e0cd2e6f1fb4d88f88dd794b`, as recorded in
[the July ingest record](../ingest-runs/2026-07-23-us-cfr-416-deeming-and-irs-notice-2025-67.md).
The historical producer includes body normalization changes made after that
artifact was produced. The regression test preserves the producer's replay
baseline and checks the retained July artifact separately. This validation does
not regenerate, replace, or republish the checked-in corpus.

The producer and PR base `17f9ace7291d4c1c284eb2007422dded17bba2f3` have identical
generator, environment files, complete `src/axiom_corpus` tree, and retained
source directory. The manifest supplies SHA-256 hashes for the generator,
principal ingestion modules, lockfile, and Python/project configuration, plus
Git tree object IDs covering all package code and the source directory. These
are historical identities, not pins on the implementation under test.

## Verify the producer and base

Run from a repository checkout containing both historical commits. This reads
Git objects, including source snapshots, without checking out or modifying the
protected artifacts:

```bash
python3 - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

manifest = json.loads(Path("docs/validation/us-cfr-416-deeming-baseline.json").read_text())
producer = manifest["producer"]
for commit in (producer["commit"], producer["equivalent_base_commit"]):
    expected_files = dict(producer["files_sha256"])
    expected_files.update({
        f"data/corpus/{path}": digest
        for path, digest in manifest["source_sha256"].items()
    })
    for path, expected in expected_files.items():
        content = subprocess.check_output(["git", "show", f"{commit}:{path}"])
        assert hashlib.sha256(content).hexdigest() == expected, (commit, path)
    for path, expected in producer["git_tree_oid"].items():
        actual = subprocess.check_output(
            ["git", "rev-parse", f"{commit}:{path}"], text=True
        ).strip()
        assert actual == expected, (commit, path)
print("Producer and base identities verified")
PY
```

## Replay with the producer's locked environment

The verified runtime was CPython 3.14.4 with uv 0.11.7 on macOS arm64. The
following commands create a sparse historical checkout and put the environment,
report, and all five outputs in a new external temporary directory. Sparse
checkout avoids copying unrelated corpus data. The destination must remain
external; do not substitute `data/corpus` for `--base`.

Run from the current repository checkout with those runtime versions available:

```bash
replay_root=$(mktemp -d "${TMPDIR:-/tmp}/cfr416-baseline.XXXXXX")
cp docs/validation/us-cfr-416-deeming-baseline.json "$replay_root/manifest.json"
git worktree add --detach --no-checkout "$replay_root/producer" \
  f22e9a458aa23ce8d0d28f05c58d2fe25360c8fc
git -C "$replay_root/producer" sparse-checkout set --no-cone \
  /src/ /scripts/repro_us_cfr_416_deeming_slice.py \
  /pyproject.toml /uv.lock /README.md /.python-version \
  /data/corpus/sources/us/regulation/2026-07-23-title-20-part-416/
git -C "$replay_root/producer" checkout --detach \
  f22e9a458aa23ce8d0d28f05c58d2fe25360c8fc
cd "$replay_root/producer"
UV_PROJECT_ENVIRONMENT="$replay_root/locked-venv" \
  uv sync --frozen --no-install-project --python 3.14.4
UV_PROJECT_ENVIRONMENT="$replay_root/locked-venv" PYTHONPATH=src \
  uv run --frozen --no-sync --python 3.14.4 \
  python scripts/repro_us_cfr_416_deeming_slice.py \
  --source-base data/corpus --base "$replay_root/output" > "$replay_root/report.json"
"$replay_root/locked-venv/bin/python" - "$replay_root" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads((root / "manifest.json").read_text())
report = json.loads((root / "report.json").read_text())
for key, expected in manifest["expected_report"].items():
    assert report[key] == expected, key
assert report["files"] == manifest["output_sha256"]
for path, expected in manifest["output_sha256"].items():
    actual = hashlib.sha256((root / "output" / path).read_bytes()).hexdigest()
    assert actual == expected, path
print("All five replay outputs and scope checks verified")
PY
```

`uv sync --frozen` uses the producer's recorded dependency resolution;
`--no-install-project` avoids an unpinned package build environment. `PYTHONPATH`
loads the producer's checked-out source, and `uv run --no-sync` keeps the synced
environment intact. The generator verifies both source SHA-256 hashes before
performing extraction. No network source refresh is part of this replay.

The normal regression test checks the manifest's source hashes against both the
generator pins and the retained bytes, compares all five generated hashes, and
retains the independent 622/14 assertions. It does not require historical Git
objects, so it also runs in a shallow CI checkout.
