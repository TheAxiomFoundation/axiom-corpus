#!/usr/bin/env bash
# Install a checkout of this project on exactly the versions its uv.lock pins.
#
# usage: install-locked.sh [--project DIR] [--editable] [--extra NAME]...
#
# CI installs through this script, so the tests, the corpus guard and the
# release validators run on the versions `uv sync` and `uv run` give a
# developer (docs/dependency-lock.md). It installs into the Python on PATH:
#
#   1. uv, at the version and hashes in uv-requirements.txt next to this file.
#   2. Every dependency DIR/uv.lock pins for the project and the named extras:
#      `uv export --frozen` writes them as pip requirements with hashes, and
#      pip installs them with --require-hashes.
#   3. The project in DIR itself, without resolving dependencies again.
#
# DIR defaults to $GITHUB_WORKSPACE, or the current directory outside Actions.
# The lock does not pin the build backend pyproject.toml names (setuptools);
# pip fetches it to build the project in step 3.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="${GITHUB_WORKSPACE:-$PWD}"
editable=0
extras=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      project="$2"
      shift 2
      ;;
    --editable)
      editable=1
      shift
      ;;
    --extra)
      extras+=(--extra "$2")
      shift 2
      ;;
    *)
      echo "install-locked.sh: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done
project="$(cd "$project" && pwd)"
if [ ! -f "$project/uv.lock" ]; then
  echo "install-locked.sh: $project has no uv.lock" >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# pip and uv run from an empty directory with python -I, so nothing in a
# checkout can shadow what they import.
cd "$work"

python -I -m pip install --require-hashes -r "$here/uv-requirements.txt"
# --frozen: the lock as committed. tests/test_locked_install.py checks that it
# still matches pyproject.toml.
UV_PYTHON_DOWNLOADS=never python -I -m uv export \
  --quiet \
  --frozen \
  --no-emit-project \
  --project "$project" \
  ${extras[@]+"${extras[@]}"} \
  --output-file "$work/requirements.txt"
python -I -m pip install --require-hashes -r "$work/requirements.txt"
if [ "$editable" = "1" ]; then
  python -I -m pip install --no-deps -e "$project"
else
  python -I -m pip install --no-deps "$project"
fi
