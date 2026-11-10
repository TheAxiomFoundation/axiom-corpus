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
- every release job's checkout persists no credentials for the install to read;
- every job in .github/workflows/ that runs this project's code or Python
  installs it through install-locked.sh first, and every install form named
  by _INSTALL counts as an install. These checks read ``run:`` blocks; they
  guard against mistakes, not against a workflow written to get around them.

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
from hypothesis import given
from hypothesis import strategies as st
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

# Workflows that may install outside install-locked.sh. None may: the release
# workflows (publish, activate-release, register-release-object and
# mirror-release) moved to the lock in axiom-corpus#866, so the versions that
# sign, publish, register, mirror and activate releases are the ones CI tests.
WORKFLOWS_NOT_YET_LOCKED: set[str] = set()
RELEASE_WORKFLOWS = (
    "publish.yml",
    "activate-release.yml",
    "register-release-object.yml",
    "mirror-release.yml",
    "export-release-artifact.yml",
)

# Named install forms, including uv's ephemeral environments. A shell separator
# ends the uv run command unless it sits inside quotes; a backslash-newline
# continues it.
_INSTALL = re.compile(
    r"\b(?:pip3?|pipx)\b[^\n;&|]*?\binstall\b"
    r"|\buv\s+(?:pip\s+install|sync|add|tool\s+(?:install|run))\b"
    r"|\buv\s+run\b(?:[^\n;&|'\"]|'[^'\n]*'|\"[^\"\n]*\"|\\\n)*?(?<!\S)--with(?:[=\s]|$)"
    r"|\buvx\b"
)
# A step that runs this project's code, its checks, or any Python code (which
# may import only third-party packages, so no project name appears).
_PROJECT_CODE = re.compile(
    r"\baxiom-corpus(?:-ingest)?\b|\bpytest\b|\bruff\b|\bmypy\b|\btowncrier\b"
    r"|\bpython3?\b|\baxiom_corpus\b"
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


def test_the_lock_doc_names_every_build_requirement_the_lock_leaves_unpinned() -> None:
    """install-locked.sh builds the project with pyproject.toml's [build-system] requirements.

    The lock pins none of them, so docs/dependency-lock.md's "What the lock does
    not pin" must quote each one in full, name and bound, as a code span exactly
    as pyproject.toml writes it, so a bound changed in one file and not the
    other fails here. Code spans, not word boundaries, because a requirement can
    end in a quote (a marker such as ``python_version < '3.11'``), and ``\\b``
    never matches between that quote and a backtick or a space.
    """
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires = pyproject["build-system"]["requires"]
    doc = (ROOT / "docs" / "dependency-lock.md").read_text(encoding="utf-8")
    section = doc.split("## What the lock does not pin", 1)[1].split("\n## ", 1)[0]
    unquoted = [requirement for requirement in requires if f"`{requirement}`" not in section]
    assert not unquoted, (
        'docs/dependency-lock.md\'s "What the lock does not pin" does not quote these '
        f"[build-system] requirements as pyproject.toml writes them: {unquoted}"
    )


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


def _step_shell(document: dict, job: dict, step: dict) -> str:
    """The shell that runs a step: its own, else the job's default, else the workflow's."""
    for scope in (
        step,
        job.get("defaults", {}).get("run", {}),
        document.get("defaults", {}).get("run", {}),
    ):
        if scope.get("shell"):
            return str(scope["shell"])
    return ""


def _steps(workflow: Path) -> dict[str, list[tuple[str, str]]]:
    """Job name -> its steps' (name, commands), in order; steps without run are ''.

    The commands start with the step's shell, since `shell: python` runs the
    block as Python with no python command in it.
    """
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return {
        job_name: [
            (
                step.get("name", f"step {index + 1}"),
                f"{_step_shell(document, job, step)}\n{step['run']}" if "run" in step else "",
            )
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


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS.glob("*.yml")), ids=lambda path: path.name)
def test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow: Path) -> None:
    uninstalled = []
    for job, steps in _steps(workflow).items():
        first = next(
            (index for index, (_, run) in enumerate(steps) if _PROJECT_CODE.search(run)), None
        )
        if first is None:
            continue
        if not any("install-locked.sh" in run for _, run in steps[: first + 1]):
            uninstalled.append(f"{job}: {steps[first][0]}")
    assert not uninstalled, (
        f"these {workflow.name} steps run project code before any install-locked.sh step: "
        f"{uninstalled}"
    )


def test_only_the_listed_release_workflows_install_outside_the_lock() -> None:
    bare = {
        workflow.name
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        if _installs_outside_the_script(workflow)
    }
    assert bare == WORKFLOWS_NOT_YET_LOCKED


@pytest.mark.parametrize("workflow_name", RELEASE_WORKFLOWS)
def test_release_checkouts_do_not_persist_credentials(workflow_name: str) -> None:
    document = yaml.safe_load((WORKFLOWS / workflow_name).read_text(encoding="utf-8"))
    for job_name, job in document["jobs"].items():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                assert step.get("with", {}).get("persist-credentials") is False, (
                    f"{workflow_name}: {job_name} checkout must set persist-credentials: false"
                )


@pytest.mark.parametrize(
    "run",
    [
        'python -c "import boto3"',
        'python3 -I -c "import boto3"',
        "python <<'PY'\nimport boto3\nPY\n",
        "python - <<'PY'\nimport boto3\nPY\n",
        "python3 - <<'PY'\nimport boto3\nPY\n",
        "python third_party_only.py",
    ],
)
def test_python_steps_require_the_locked_install(tmp_path: Path, run: str) -> None:
    workflow = tmp_path / "python.yml"
    workflow.write_text(
        yaml.safe_dump(
            {
                "jobs": {
                    "example": {
                        "steps": [
                            {"name": "early Python", "run": run},
                            {"run": "bash .github/scripts/install-locked.sh --editable"},
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="example: early Python"):
        test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow)


@pytest.mark.parametrize(
    ("step_shell", "job_defaults", "workflow_defaults"),
    [
        ("python", None, None),
        ("python3 -u {0}", None, None),
        (None, "python", None),
        (None, None, "python"),
    ],
)
def test_python_shell_steps_require_the_locked_install(
    tmp_path: Path, step_shell: str | None, job_defaults: str | None, workflow_defaults: str | None
) -> None:
    early = {"name": "early Python", "run": "import boto3"}
    if step_shell:
        early["shell"] = step_shell
    job: dict = {"steps": [early, {"run": "bash .github/scripts/install-locked.sh --editable"}]}
    if job_defaults:
        job["defaults"] = {"run": {"shell": job_defaults}}
    document: dict = {"jobs": {"example": job}}
    if workflow_defaults:
        document["defaults"] = {"run": {"shell": workflow_defaults}}
    workflow = tmp_path / "python-shell.yml"
    workflow.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(AssertionError, match="example: early Python"):
        test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow)


def test_mirror_dependency_import_cannot_move_before_the_locked_install(tmp_path: Path) -> None:
    document = yaml.safe_load((WORKFLOWS / "mirror-release.yml").read_text(encoding="utf-8"))
    steps = document["jobs"]["mirror"]["steps"]
    gate = next(
        step
        for step in steps
        if step.get("name") == "Fetch canonical object and run deterministic mirror gate"
    )
    assert "import boto3\n" in gate["run"]
    gate["run"] = gate["run"].replace("import boto3\n", "")
    install_index = next(
        index for index, step in enumerate(steps) if "install-locked.sh" in step.get("run", "")
    )
    steps.insert(
        install_index,
        {
            "name": "Import mirror dependency before install",
            "run": "python - <<'PY'\nimport boto3\nPY\n",
        },
    )
    workflow = tmp_path / "mirror-release.yml"
    workflow.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(AssertionError, match="mirror: Import mirror dependency before install"):
        test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow)


# Each named form gets its own examples and property test, so omitting one
# alternative cannot be hidden by Hypothesis sampling a different form.
_INSTALL_FORMS = (
    "pip install boto3",
    "pip3 -q install boto3",
    "pipx install ruff",
    "uv pip install boto3",
    "uv sync --extra dev",
    "uv add boto3",
    "uv tool install ruff",
    "uv run --with boto3 python -c 'import boto3'",
    "uv run --with=boto3 python -c 'import boto3'",
    "uv run --offline --with boto3 python -c 'import boto3'",
    "uv run \\\n  --with boto3 python -c 'import boto3'",
    "uv run --index-url 'https://example.invalid/simple?a=1&b=2' --with boto3 python",
    'uv run --index-url "https://example.invalid/simple?a=1&b=2" --with boto3 python',
    "uvx ruff check .",
    "uv tool run ruff check .",
)


@pytest.mark.parametrize("command", _INSTALL_FORMS)
def test_each_named_install_form_matches(command: str) -> None:
    assert _INSTALL.search(command)


@pytest.mark.parametrize("command", _INSTALL_FORMS)
@given(prefix=st.text(max_size=100), suffix=st.text(max_size=100))
def test_install_forms_match_in_surrounding_shell_text(
    command: str, prefix: str, suffix: str
) -> None:
    assert _INSTALL.search(f"{prefix}\n{command}\n{suffix}")


_NON_INSTALL_COMMANDS = (
    "uv run --extra dev pytest -q",
    "uv run python scripts/check_release_gate.py",
    "uv run --extra dev python -m towncrier build --draft --version 0.0.0",
    "uv run axiom-corpus-ingest --help",
    "uv run --without dev python -c 'import boto3'",
    "uv run echo ok; echo --with boto3",
    "uv run echo ok && echo --with boto3",
    "uv run echo ok | cat --with boto3",
    "uv run echo ok\necho --with boto3",
    "uv run echo 'a;b'; echo --with boto3",
    'uv run echo "a&b" && echo --with boto3',
    "uvxfoo ruff",
    "uv tool list",
    "pip list",
    "pip3 --version",
    "pipx list",
    "echo ready",
    "git status --short",
)


@pytest.mark.parametrize("command", _NON_INSTALL_COMMANDS)
def test_non_install_commands_stay_allowed(command: str) -> None:
    assert not _INSTALL.search(command)


@given(
    commands=st.lists(
        st.tuples(
            st.sampled_from(_NON_INSTALL_COMMANDS),
            # Independently generated arguments cannot spell an install form.
            st.text(alphabet="abcxyz0123456789_./-", max_size=30),
        ),
        min_size=1,
        max_size=10,
    ),
    separator=st.sampled_from(("\n", "; ", " && ", " || ", " | ")),
)
def test_generated_commands_without_install_forms_stay_allowed(
    commands: list[tuple[str, str]], separator: str
) -> None:
    run = separator.join(f"{command} '{argument}'" for command, argument in commands)
    assert not _INSTALL.search(run)


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
