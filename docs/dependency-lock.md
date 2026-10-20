# Locked CI and export dependencies

CI and the authenticated release-artifact exporter install the dependency versions
in the checked-out `uv.lock` through `.github/scripts/install-locked.sh`. The
installer, its hash-pinned uv requirements, lock updates and installation tests
are carried from axiom-corpus PR #867, commit
`5cd1f8fc94ea3b70dcb41006b9b162a274866743`. This integration does not include that
PR's PDF comparison tool or make claims about its extraction measurements.

The installer runs Python in isolated mode from a temporary directory, installs
uv with required hashes, exports the committed lock without resolving updates,
and installs dependencies with required hashes and wheels only. It installs the
project itself with `--no-deps`. The project's setuptools build backend is not
pinned by this lock and pip can fetch it to build the project.

On pull requests, the corpus guard continues to execute the base commit's code
with the base commit's lock. It uses the base's installer when present. For a
base predating the installer, it uses this branch's installer with the explicit
`--allow-source-builds` option: the old lock may lack Python 3.14 wheels, and
build tools fetched for those source distributions are not hash-checked by this
installer. Review of workflow and installer changes remains a trust boundary.
The existing artifact guard, attestation, remote-object checks, release-content
baseline and test thresholds remain in place.

The exporter installs before receiving read-only storage credentials, then runs
its script directly with that installed Python. It does not create a second uv
environment. The other release workflows remain outside this integration; their
existing installation behavior and signing/publication rules are unchanged.

The carried lock adds the test plugins used by CI, their dependencies, and the
PR #867 pyiceberg 0.12.0 / zstandard wheel-compatible dependency change. Extraction
library versions remain as pinned in the existing lock. This is installation
reproducibility work, not a corpus re-extraction or release activation.
