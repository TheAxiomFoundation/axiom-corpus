#!/usr/bin/env bash
# Install a checkout of this project on exactly the versions its uv.lock pins.
#
# usage: install-locked.sh [--project DIR] [--editable] [--extra NAME]...
#                          [--allow-source-builds]
#
# CI installs through this script, so the tests, the corpus guard and the
# release validators run on the versions `uv sync` and `uv run` give a
# developer (docs/dependency-lock.md). It installs into the Python on PATH:
#
#   1. uv, at the version and hashes in uv-requirements.txt next to this file.
#   2. Every dependency DIR/uv.lock pins for the project and the named extras:
#      `uv export --frozen` writes them as pip requirements with hashes, and
#      pip installs them with --require-hashes, from wheels only.
#   3. The project in DIR itself, without resolving dependencies again.
#
# Wheels only, because pip does not hash-check the tools it would fetch to
# build a source distribution. --allow-source-builds lifts that, for a lock
# from before the rule (tests/test_locked_install.py keeps a wheel for every
# locked package): CI's guard install on a pull request whose base commit
# predates this script.
#
# DIR defaults to $GITHUB_WORKSPACE, or the current directory outside Actions.
# The lock does not pin the build backend pyproject.toml names (setuptools);
# pip fetches it to build the project in step 3.
set -euo pipefail

usage() {
  echo "install-locked.sh: $1" >&2
  echo "usage: install-locked.sh [--project DIR] [--editable] [--extra NAME]... [--allow-source-builds]" >&2
  exit 2
}

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="${GITHUB_WORKSPACE:-$PWD}"
editable=0
binary=(--only-binary :all:)
extras=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project)
      [ "$#" -ge 2 ] || usage "--project needs a directory"
      project="$2"
      shift 2
      ;;
    --editable)
      editable=1
      shift
      ;;
    --extra)
      [ "$#" -ge 2 ] || usage "--extra needs a name"
      extras+=(--extra "$2")
      shift 2
      ;;
    --allow-source-builds)
      binary=()
      shift
      ;;
    *)
      usage "unknown argument: $1"
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

python -I -m pip install --require-hashes --only-binary :all: -r "$here/uv-requirements.txt"
# --frozen: the lock as committed. tests/test_locked_install.py checks that it
# still matches pyproject.toml.
UV_PYTHON_DOWNLOADS=never python -I -m uv export \
  --quiet \
  --frozen \
  --no-emit-project \
  --project "$project" \
  ${extras[@]+"${extras[@]}"} \
  --output-file "$work/requirements.txt"
python -I -m pip install --require-hashes ${binary[@]+"${binary[@]}"} -r "$work/requirements.txt"
if [ "$editable" = "1" ]; then
  python -I -m pip install --no-deps -e "$project"
else
  python -I -m pip install --no-deps "$project"
fi
