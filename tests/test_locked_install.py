"""CI and local runs install the same versions: the ones uv.lock pins.

Before this file existed CI installed with ``pip install -e .[dev]`` against
the lower bounds in pyproject.toml, so it ran whatever PyPI served that day:
PyMuPDF 1.28.2 where the lock pins 1.26.7, and two extraction tests could only
run locally. docs/dependency-lock.md has the measurements. These tests hold the
agreement in place:

- every locked package that is installed is at its locked version, and every
  package the lock pins for the ``dev`` extra on this platform is installed
  (in CI, this is the check that the workflow installed the lock);
- ``uv lock --check``: uv.lock is up to date with pyproject.toml;
- every locked package has a wheel for CI's platform, which install-locked.sh
  requires;
- every job in .github/workflows/ci.yml that runs this project's code installs
  it through install-locked.sh, and no step there installs packages any other
  way. That check reads the commands in ``run:`` blocks; it guards against
  mistakes, not against a workflow written to get around it.

Installed packages the lock does not name are not flagged: on a pull request
CI installs the base commit's lock first (for the corpus guard) into the same
Python, so a package the pull request drops stays installed.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections import defaultdict
from importlib import metadata
from pathlib import Path

import pytest
import yaml
from packaging import tags
from packaging.markers import Marker
from packaging.utils import canonicalize_name, parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
INSTALL_SCRIPT = ROOT / ".github" / "scripts" / "install-locked.sh"
PROJECT = "axiom-corpus"

# CI runs CPython 3.14 on ubuntu-latest (Ubuntu 24.04, glibc 2.39), x86_64.
CI_PYTHON = (3, 14)
CI_GLIBC_MINOR = 39

# Release workflows that still install with a bare `pip install -e .`
# (axiom-corpus#866). They run no extraction and no tests; moving them changes
# the versions that sign and publish releases, so it is a change of its own.
# Remove a name here in the pull request that moves its workflow to
# install-locked.sh.
WORKFLOWS_NOT_YET_LOCKED = {
    "activate-release.yml",
    "mirror-release.yml",
    "publish.yml",
    "register-release-object.yml",
}

# A package install by pip (options may sit between `pip` and `install`), pipx
# or uv.
_INSTALL = re.compile(
    r"\b(?:pip3?|pipx)\b[^\n;&|]*?\binstall\b|\buv\s+(?:pip\s+install|sync|add|tool\s+install)\b"
)
# A step that runs this project's code or its checks.
_PROJECT_CODE = re.compile(
    r"\baxiom-corpus(?:-ingest)?\b|\bpytest\b|\bruff\b|\bmypy\b|\btowncrier\b"
    r"|python3?\s+(?:-I\s+)?scripts/|\baxiom_corpus\b"
)


def _lock() -> dict:
    return tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))


def _locked_versions() -> dict[str, set[str]]:
    versions: dict[str, set[str]] = defaultdict(set)
    for package in _lock()["package"]:
        if "version" in package:
            versions[canonicalize_name(package["name"])].add(package["version"])
    return versions


def _installed() -> dict[str, str]:
    return {
        canonicalize_name(distribution.metadata["Name"]): distribution.version
        for distribution in metadata.distributions()
    }


def _uv() -> list[str]:
    """The uv command: the module install-locked.sh installs, or uv on PATH."""
    if importlib.util.find_spec("uv") is not None:
        return [sys.executable, "-m", "uv"]
    if path := shutil.which("uv"):
        return [path]
    if os.environ.get("CI"):
        pytest.fail("uv is not installed; .github/scripts/install-locked.sh installs it in CI")
    pytest.skip("uv is not installed")


def _run_uv(*arguments: str) -> str:
    env = {**os.environ, "UV_PYTHON": sys.executable, "UV_PYTHON_DOWNLOADS": "never"}
    result = subprocess.run(
        [*_uv(), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_installed_locked_packages_are_at_their_locked_versions() -> None:
    locked = _locked_versions()
    differing = {
        name: (version, sorted(locked[name]))
        for name, version in _installed().items()
        if name in locked and version not in locked[name]
    }
    assert not differing, (
        "installed versions differ from uv.lock (installed, locked): "
        f"{differing}. Install with `uv sync --extra dev`; CI installs with "
        ".github/scripts/install-locked.sh."
    )


def test_every_package_the_lock_pins_for_the_dev_extra_is_installed() -> None:
    exported = _run_uv(
        "export", "--frozen", "--offline", "--no-emit-project", "--no-hashes",
        "--no-header", "--no-annotate", "--extra", "dev",
    )  # fmt: skip
    installed = _installed()
    missing = []
    for line in exported.splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "-")):
            continue
        requirement, _, marker = line.partition(";")
        name, _, version = requirement.strip().partition("==")
        if marker.strip() and not Marker(marker.strip()).evaluate():
            continue
        if installed.get(canonicalize_name(name)) != version:
            missing.append(
                f"{name}=={version} (installed: {installed.get(canonicalize_name(name))})"
            )
    assert not missing, (
        f"the lock pins these for the dev extra, but they are not installed: {missing}"
    )


def test_lock_is_up_to_date_with_pyproject() -> None:
    """A pyproject.toml change without `uv lock` fails here (`uv lock --check`)."""
    _run_uv("lock", "--check", "--offline")


def _ci_wheel_tags() -> set[tags.Tag]:
    platforms = [f"manylinux_2_{minor}_x86_64" for minor in range(CI_GLIBC_MINOR, 4, -1)]
    platforms += [
        "manylinux2014_x86_64",
        "manylinux2010_x86_64",
        "manylinux1_x86_64",
        "linux_x86_64",
    ]
    interpreter = f"cp{CI_PYTHON[0]}{CI_PYTHON[1]}"
    return {
        *tags.cpython_tags(CI_PYTHON, abis=[interpreter], platforms=platforms),
        *tags.compatible_tags(CI_PYTHON, interpreter=interpreter, platforms=platforms),
    }


def test_every_locked_package_has_a_wheel_for_ci() -> None:
    """install-locked.sh installs wheels only (pip does not hash-check build tools)."""
    supported = _ci_wheel_tags()
    without_wheel = []
    for package in _lock()["package"]:
        if canonicalize_name(package["name"]) == PROJECT:
            continue
        filenames = [wheel["url"].rsplit("/", 1)[1] for wheel in package.get("wheels", [])]
        if not any(parse_wheel_filename(name)[3] & supported for name in filenames):
            without_wheel.append(f"{package['name']} {package.get('version')}")
    assert not without_wheel, (
        "uv.lock pins packages with no wheel for CPython "
        f"{CI_PYTHON[0]}.{CI_PYTHON[1]} on manylinux x86_64: {without_wheel}"
    )


def _steps(workflow: Path) -> dict[str, list[tuple[str, str]]]:
    """Job name -> its steps' (name, run block), in order; steps without run are ''."""
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return {
        job_name: [
            (step.get("name", f"step {index + 1}"), str(step.get("run", "")))
            for index, step in enumerate(job.get("steps", []))
        ]
        for job_name, job in document["jobs"].items()
    }


def _installs_outside_the_script(workflow: Path) -> list[str]:
    return [
        f"{job}: {name}"
        for job, steps in _steps(workflow).items()
        for name, run in steps
        if _INSTALL.search(run)
    ]


def test_ci_workflow_installs_only_through_the_locked_script() -> None:
    bare = _installs_outside_the_script(WORKFLOWS / "ci.yml")
    assert not bare, f"ci.yml steps install outside install-locked.sh: {bare}"


def test_every_ci_job_that_runs_project_code_installs_it_from_the_lock() -> None:
    uninstalled = []
    for job, steps in _steps(WORKFLOWS / "ci.yml").items():
        first = next(
            (index for index, (_, run) in enumerate(steps) if _PROJECT_CODE.search(run)), None
        )
        if first is None:
            continue
        if not any("install-locked.sh" in run for _, run in steps[: first + 1]):
            uninstalled.append(f"{job}: {steps[first][0]}")
    assert not uninstalled, (
        f"these ci.yml steps run project code before any install-locked.sh step: {uninstalled}"
    )


def test_only_the_listed_release_workflows_install_outside_the_lock() -> None:
    bare = {
        workflow.name
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        if _installs_outside_the_script(workflow)
    }
    assert bare == WORKFLOWS_NOT_YET_LOCKED


@pytest.mark.parametrize(
    "command",
    [
        "pip install -e .",
        "python -I -m pip install --upgrade pip",
        "python -m pip --disable-pip-version-check install foo",
        "pip3 -q install foo",
        "uv pip install foo",
        "uv sync --extra dev",
        "pipx install ruff",
    ],
)
def test_the_install_pattern_finds_install_commands(command: str) -> None:
    assert _INSTALL.search(command)


@pytest.mark.parametrize(
    "command",
    [
        "bash .github/scripts/install-locked.sh --editable",
        "pip --version; echo install",
        "pip list",
    ],
)
def test_the_install_pattern_ignores_other_commands(command: str) -> None:
    assert not _INSTALL.search(command)


def test_install_script_installs_dependencies_only_with_hashes_from_wheels() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    commands = re.sub(r"\\\n\s*", " ", script)
    installs = [
        line.strip()
        for line in commands.splitlines()
        if _INSTALL.search(line) and not line.lstrip().startswith("#")
    ]
    assert len(installs) == 4
    dependencies = [line for line in installs if "--no-deps" not in line]
    assert len(dependencies) == 2  # uv, then the exported lock
    for line in dependencies:
        assert "--require-hashes" in line, line
    assert "--only-binary :all:" in dependencies[0]
    assert '${binary[@]+"${binary[@]}"}' in dependencies[1]
    assert "binary=(--only-binary :all:)" in commands
    assert "export" in commands and "--frozen" in commands


@pytest.mark.parametrize(
    ("arguments", "returncode", "message"),
    [
        (["--no-such-option"], 2, "unknown argument"),
        (["--project"], 2, "--project needs a directory"),
        (["--extra"], 2, "--extra needs a name"),
        (["--project", "{empty}"], 1, "has no uv.lock"),
    ],
)
def test_install_script_refuses_before_installing(
    tmp_path: Path, arguments: list[str], returncode: int, message: str
) -> None:
    arguments = [argument.format(empty=tmp_path) for argument in arguments]
    result = subprocess.run(
        ["bash", str(INSTALL_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert result.returncode == returncode
    assert message in result.stderr
    assert result.stdout == ""
