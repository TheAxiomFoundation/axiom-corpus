"""CI and local runs install the same versions: the ones uv.lock pins.

Before this file existed CI installed with ``pip install -e .[dev]`` against
the lower bounds in pyproject.toml, so it ran whatever PyPI served that day:
PyMuPDF 1.28.2 where the lock pins 1.26.7, and two extraction tests could only
run locally. docs/dependency-lock.md has the measurements. These tests hold the
agreement in place:

- the environment running the tests has every locked package at its locked
  version (in CI, this is the check that the workflow installed the lock);
- uv.lock records the requirements pyproject.toml declares;
- every locked package has a wheel for CI's platform, so CI builds nothing
  but this project from source;
- .github/workflows/ci.yml installs only through install-locked.sh.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from collections import defaultdict
from importlib import metadata
from pathlib import Path

import pytest
import yaml
from packaging import tags
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
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

_PIP_INSTALL = re.compile(r"\bpip3?\s+install\b")


def _lock() -> dict:
    return tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))


def _locked_versions() -> dict[str, set[str]]:
    versions: dict[str, set[str]] = defaultdict(set)
    for package in _lock()["package"]:
        if "version" in package:
            versions[canonicalize_name(package["name"])].add(package["version"])
    return versions


def test_environment_has_every_locked_package_at_its_locked_version() -> None:
    locked = _locked_versions()
    installed = {
        canonicalize_name(distribution.metadata["Name"]): distribution.version
        for distribution in metadata.distributions()
    }
    differing = {
        name: (version, sorted(locked[name]))
        for name, version in installed.items()
        if name in locked and version not in locked[name]
    }
    assert not differing, (
        "installed versions differ from uv.lock (installed, locked): "
        f"{differing}. Install with `uv sync --extra dev`; CI installs with "
        ".github/scripts/install-locked.sh."
    )
    # The comparison above is empty for a package that is not installed at all.
    project_requirements = {
        canonicalize_name(entry["name"])
        for entry in _project_lock_entry()["metadata"]["requires-dist"]
        if "marker" not in entry
    }
    assert project_requirements - installed.keys() == set()


def _project_lock_entry() -> dict:
    return next(
        package for package in _lock()["package"] if canonicalize_name(package["name"]) == PROJECT
    )


def _requirement_key(name: str, specifier: str, extra: str | None) -> tuple[str, str, str | None]:
    return (canonicalize_name(name), str(SpecifierSet(specifier)), extra)


def test_lock_records_the_requirements_pyproject_declares() -> None:
    """A pyproject.toml dependency change without `uv lock` fails here."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = set()
    for line in project["dependencies"]:
        requirement = Requirement(line)
        declared.add(_requirement_key(requirement.name, str(requirement.specifier), None))
    for extra, lines in project["optional-dependencies"].items():
        for line in lines:
            requirement = Requirement(line)
            declared.add(_requirement_key(requirement.name, str(requirement.specifier), extra))

    lock_metadata = _project_lock_entry()["metadata"]
    locked = set()
    for entry in lock_metadata["requires-dist"]:
        extra_match = re.search(r"extra == '([^']+)'", entry.get("marker", ""))
        locked.add(
            _requirement_key(
                entry["name"],
                entry.get("specifier", ""),
                extra_match.group(1) if extra_match else None,
            )
        )

    assert declared == locked, (
        "uv.lock is out of date with pyproject.toml; run `uv lock`. "
        f"Only in pyproject.toml: {sorted(declared - locked, key=str)}. "
        f"Only in uv.lock: {sorted(locked - declared, key=str)}."
    )
    assert set(lock_metadata["provides-extras"]) == set(project["optional-dependencies"])


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
    """A package with only an sdist would be built in CI with unpinned build tools."""
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


def _run_blocks(workflow: Path) -> list[tuple[str, str]]:
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    blocks = []
    for job_name, job in document["jobs"].items():
        for index, step in enumerate(job.get("steps", [])):
            if "run" in step:
                blocks.append((f"{job_name}: {step.get('name', f'step {index + 1}')}", step["run"]))
    return blocks


def test_ci_workflow_installs_only_through_the_locked_script() -> None:
    blocks = _run_blocks(WORKFLOWS / "ci.yml")
    bare = [label for label, run in blocks if _PIP_INSTALL.search(run)]
    assert not bare, f"ci.yml steps install outside install-locked.sh: {bare}"
    assert sum(run.count("install-locked.sh") for _, run in blocks) >= 5


def test_only_the_listed_release_workflows_install_outside_the_lock() -> None:
    bare = {
        workflow.name
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        if any(_PIP_INSTALL.search(run) for _, run in _run_blocks(workflow))
    }
    assert bare == WORKFLOWS_NOT_YET_LOCKED


def test_install_script_installs_dependencies_only_with_hashes() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    commands = re.sub(r"\\\n\s*", " ", script)
    installs = [
        line.strip()
        for line in commands.splitlines()
        if _PIP_INSTALL.search(line) and not line.lstrip().startswith("#")
    ]
    assert len(installs) == 4
    for line in installs:
        # Only the project itself, already-resolved, installs without hashes.
        assert "--require-hashes" in line or "--no-deps" in line, line
    assert "export" in commands and "--frozen" in commands


@pytest.mark.parametrize(
    ("arguments", "returncode", "message"),
    [
        (["--no-such-option"], 2, "unknown argument"),
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
