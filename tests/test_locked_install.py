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
  installs it through install-locked.sh first, and every install form
  _command_installs names counts as an install. These checks read each step's
  shell words; they guard against mistakes, not against a workflow written to
  get around them.

Installed packages the lock does not name are not flagged: on a pull request
CI installs the base commit's lock first (for the corpus guard) into the same
Python, so a package the pull request drops stays installed.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import tomllib
from collections import defaultdict
from collections.abc import Iterator
from importlib import metadata
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml
from hypothesis import given, settings
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

# A step that runs this project's code, its checks, or any Python code (which
# may import only third-party packages, so no project name appears).
_PROJECT_CODE = re.compile(
    r"\baxiom-corpus(?:-ingest)?\b|\bpytest\b|\bruff\b|\bmypy\b|\btowncrier\b"
    r"|\bpython3?\b|\baxiom_corpus\b"
)
# The same programs as whole names, for a step's `shell`.
_PROJECT_PROGRAM = re.compile(
    r"axiom-corpus(?:-ingest)?|axiom_corpus|pytest|ruff|mypy|towncrier|python[\d.]*"
)
# Programs that read a step's block as shell text. Their arguments, such as
# `bash --rcfile /some/path/python.rc {0}`, don't say what the block runs.
_SHELLS = frozenset({"bash", "sh", "dash", "zsh", "ksh", "fish", "pwsh", "powershell", "cmd"})


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


# The install check reads shell text three ways, each one pass left to right:
#
# - as the shell reads it, so quotes and escapes decide where words and commands end;
# - line by line, with quotes closing at each line's end, so a quote this reader
#   misjudges (one in a heredoc body, say) can't hide an install on a later line;
# - each quoted word again as a script of its own, because `bash -c 'uv sync'`,
#   `eval "uv sync"` and `cmd="uv sync"` can run it. `echo 'uv sync'` counts too.
#
# Quoting a word again at least doubles the backslashes or quotes around it, so the
# rereads nest at most about log2(n) deep over n characters and the scan stays
# close to linear (test_the_install_scan_stays_within_its_time_bound).

_Enclosing = tuple[str, str, list[str], list[str] | None, bool]
# A word without these holds nothing that a second reading could split.
_READ_AGAIN = re.compile(r"""[\s;&|()`'"\\]""")
_ASSIGNMENT = re.compile(r"[^\s=]+=")
# The runner replaces ${{ ... }} before the shell starts, with text this check
# can't see, so it reads like any other expansion.
_GITHUB_EXPRESSION = re.compile(r"\$\{\{[^\n]{0,200}?\}\}")
_ANSI_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


class _ShellReader:
    """The commands and quoted words one pass found, and where the pass stands."""

    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.quoted: list[str] = []
        self.words: list[str] = []
        self.word: list[str] | None = None
        self.quote = ""
        self.next_word_is_target = False
        # What each open $(...), (...), ${...} or `...` interrupted, innermost last.
        self.enclosing: list[_Enclosing] = []

    def extend_word(self, text: str) -> None:
        if self.word is None:
            self.word = []
        self.word.append(text)

    def open_quote(self, quote: str) -> None:
        self.extend_word("")
        self.quote = quote

    def end_word(self) -> None:
        if self.word is None:
            return
        word = "".join(self.word)
        self.word = None
        if _READ_AGAIN.search(word):
            assignment = _ASSIGNMENT.match(word)
            self.quoted.append(word[assignment.end() :] if assignment else word)
        if self.next_word_is_target:
            self.next_word_is_target = False
        else:
            self.words.append(word)

    def end_command(self) -> None:
        self.end_word()
        if self.words:
            self.commands.append(self.words)
        self.words = []
        self.next_word_is_target = False

    def redirect(self, *, follows_digit: bool) -> None:
        """A redirect's file descriptor and target are not arguments of the command."""
        if follows_digit and self.word is not None and "".join(self.word).isdigit():
            self.word = None
        self.end_word()
        self.next_word_is_target = True

    def enter(self, closer: str) -> None:
        # What a substitution prints joins the word around it, as in `> $(cat name)`.
        if self.next_word_is_target and self.word is None:
            self.word = []
        self.enclosing.append((closer, self.quote, self.words, self.word, self.next_word_is_target))
        self.quote, self.words, self.word, self.next_word_is_target = "", [], None, False

    def closes(self, char: str) -> bool:
        return bool(self.enclosing) and self.enclosing[-1][0] == char

    def leave(self) -> None:
        self.end_command()
        _, self.quote, self.words, self.word, self.next_word_is_target = self.enclosing.pop()

    def at_comment(self) -> bool:
        """Whether a # starts a comment; `${#name}` holds none, and a backtick ends one."""
        return self.word is None and not (self.closes("}") or self.closes("`"))

    def toggle_backtick(self) -> None:
        if self.closes("`"):
            self.leave()
        else:
            self.enter("`")

    def end_all(self) -> None:
        while self.enclosing:
            self.leave()
        self.end_command()
        self.quote = ""


def _read_shell(text: str, *, by_line: bool = False) -> _ShellReader:
    """Split text into commands of words and collect its quoted words, in one pass.

    With by_line, each line stands alone: a newline closes every quote and ends
    every command, and a backslash-newline only ends the word, so the next line
    continues the command with a word of its own.
    """
    reader = _ShellReader()
    redirect_at = -1
    i, end = 0, len(text)
    while i < end:
        char = text[i]
        i += 1
        escapes = char == "\\" and i < end and not (by_line and text[i] == "\n")
        if char == "\n" and by_line:
            reader.end_all()
        elif reader.quote == "'":
            if char == "'":
                reader.quote = ""
            else:
                reader.extend_word(char)
        elif reader.quote == "$'":
            if char == "'":
                reader.quote = ""
            elif escapes:
                reader.extend_word(_ANSI_ESCAPES.get(text[i], text[i]))
                i += 1
            else:
                reader.extend_word(char)
        elif reader.quote == '"':
            if char == '"':
                reader.quote = ""
            elif escapes and text[i] in '"\\$`\n':
                reader.extend_word("" if text[i] == "\n" else text[i])
                i += 1
            elif char == "$" and text.startswith("(", i):
                reader.enter(")")
                i += 1
            elif char == "`":
                reader.toggle_backtick()
            else:
                reader.extend_word(char)
        elif escapes:
            if text[i] != "\n":
                reader.extend_word(text[i])
            i += 1
        elif char == "\\" and i < end:
            reader.end_word()
            reader.next_word_is_target = False
            i += 1
        elif char in " \t\r":
            reader.end_word()
        elif char in "\n;":
            reader.end_command()
        elif char == "&":
            # `2>&1` and `&>out` redirect; any other & ends the command.
            if redirect_at != i - 2 and not text.startswith(">", i):
                reader.end_command()
        elif char == "|":
            # `>|out` redirects; any other | ends the command.
            if redirect_at != i - 2:
                reader.end_command()
        elif char in "<>":
            reader.redirect(follows_digit=text[i - 2 : i - 1].isdigit())
            redirect_at = i - 1
        elif char == "(":
            reader.enter(")")
        elif char == ")":
            if reader.closes(")"):
                reader.leave()
            else:
                reader.end_command()
        elif char == "}" and reader.closes("}"):
            reader.leave()
        elif char == "`":
            reader.toggle_backtick()
        elif char in "'\"":
            reader.open_quote(char)
        elif char == "$" and text.startswith("'", i):
            reader.open_quote("$'")
            i += 1
        elif char == "$" and text.startswith('"', i):
            reader.open_quote('"')
            i += 1
        elif char == "$" and text.startswith("(", i):
            reader.enter(")")
            i += 1
        elif char == "$" and (expression := _GITHUB_EXPRESSION.match(text, i - 1)):
            reader.extend_word("$")
            i = expression.end()
        elif char == "$" and text.startswith("{", i):
            reader.extend_word("$")
            reader.enter("}")
            i += 1
        elif char == "#" and reader.at_comment():
            line_end = text.find("\n", i)
            i = end if line_end < 0 else line_end
        else:
            reader.extend_word(char)
    reader.end_all()
    return reader


def _shell_commands(text: str) -> Iterator[list[str]]:
    """Every command that text may run, as its words, by all three readings."""
    lines = _read_shell(text, by_line=True)
    yield from lines.commands
    pending = [text, *lines.quoted]
    seen: set[str] = set()
    while pending:
        script = pending.pop()
        if script not in seen:
            seen.add(script)
            reader = _read_shell(script)
            yield from reader.commands
            pending.extend(reader.quoted)


# An install form is a program among a command's words, so `sudo pip install`,
# `python -m uv sync` and `FOO=1 uvx ruff` count. A word can be a Python list item,
# since a step may run Python: ["uv", "sync"] reads as `[uv,` and `sync]`.
_PIP_PROGRAM = re.compile(r"pip(?:x|\d[\d.]*)?")
# `python -mpip` and `python -Impip` spell `python -m pip`.
_ATTACHED_MODULE = re.compile(r"^-[A-Za-z]*m(?=[A-Za-z])")
# uv run's options that install packages, per `uv run --help`. -w may close a
# cluster of short flags (-qw) or hold its value (-wboto3).
_UV_RUN_WITH = re.compile(r"--with(?:-editable|-requirements)?(?:=|$)|-[A-Za-z]*w")
# The words that lead from `uv` to an install, whatever options sit between them.
_UV_GRAMMAR = {
    "uv": {
        "add": "install",
        "sync": "install",
        "pip": "uv pip",
        "tool": "uv tool",
        "run": "uv run",
    },
    "uv pip": {"install": "install"},
    "uv tool": {"install": "install", "run": "install"},
}


def _program_name(word: str) -> str:
    """A word without list punctuation, directories or the $ and braces around a variable."""
    return word.strip("[],").rsplit("/", 1)[-1].strip("${}")


def _command_installs(words: list[str]) -> bool:
    """Whether one command's words hold an install form, in one pass over them.

    uv run takes its options ahead of the command it runs and passes the rest to
    that command, so `uv run --with x python` installs and `uv run pytest --with x`
    doesn't. No uv run option takes two values, so only a word right after an
    option can be anything but the command. That word may be the option's value, so
    the walk goes on past it: `uv run --offline pytest --with x` counts, by design,
    since this check doesn't list which options take values. A word holding an
    expansion may turn out to be options or nothing, so it ends nothing either.
    """
    saw_pip = False
    uv = ""  # how much of a uv command the words so far spell
    in_uv_run_options = False
    after_option = False
    for raw_word in words:
        word = _ATTACHED_MODULE.sub("", raw_word.strip("[],"))
        if word.startswith("-"):
            if in_uv_run_options and _UV_RUN_WITH.match(word):
                return True
            if word == "--":
                uv, in_uv_run_options = "", False
            after_option = "=" not in word
            continue
        name = _program_name(word)
        if name == "uvx" or (saw_pip and name == "install"):
            return True
        saw_pip = saw_pip or _PIP_PROGRAM.fullmatch(name) is not None
        if not word or ("$" in word and name != "uv"):
            continue
        step = "uv" if name == "uv" else _UV_GRAMMAR.get(uv, {}).get(name)
        if step == "install":
            return True
        if step or not after_option:
            uv = step or ""
        in_uv_run_options = step == "uv run" or (in_uv_run_options and after_option)
        after_option = False
    return False


def _installs(text: str) -> bool:
    return any(_command_installs(words) for words in _shell_commands(text))


def _shell_runs_project_code(shell: str) -> bool:
    """Whether a step's `shell` runs project code, as `shell: python` does with no command."""
    return any(
        _program_name(words[0]) not in _SHELLS
        and any(_PROJECT_PROGRAM.fullmatch(_program_name(word)) for word in words)
        for words in _shell_commands(shell)
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


class _Step(NamedTuple):
    name: str
    shell: str
    commands: str


def _steps(workflow: Path) -> dict[str, list[_Step]]:
    """Job name -> its steps, in order; a step without run has no shell or commands."""
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return {
        job_name: [
            _Step(
                step.get("name", f"step {index + 1}"),
                _step_shell(document, job, step) if "run" in step else "",
                step.get("run", ""),
            )
            for index, step in enumerate(job.get("steps", []))
        ]
        for job_name, job in document["jobs"].items()
    }


def _runs_project_code(step: _Step) -> bool:
    return _shell_runs_project_code(step.shell) or bool(_PROJECT_CODE.search(step.commands))


def _installs_outside_the_script(workflow: Path) -> list[str]:
    return [
        f"{job}: {step.name}"
        for job, steps in _steps(workflow).items()
        for step in steps
        if _installs(f"{step.shell}\n{step.commands}")
    ]


def test_ci_workflow_installs_only_through_the_locked_script() -> None:
    bare = _installs_outside_the_script(WORKFLOWS / "ci.yml")
    assert not bare, f"ci.yml steps install outside install-locked.sh: {bare}"


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS.glob("*.yml")), ids=lambda path: path.name)
def test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow: Path) -> None:
    uninstalled = []
    for job, steps in _steps(workflow).items():
        first = next((index for index, step in enumerate(steps) if _runs_project_code(step)), None)
        if first is None:
            continue
        if not any("install-locked.sh" in step.commands for step in steps[: first + 1]):
            uninstalled.append(f"{job}: {steps[first].name}")
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
    # uv's other spellings of --with.
    "uv run -w boto3 python",
    "uv run -qw boto3 python",
    "uv run --with-editable ./package python",
    "uv run --with-requirements extra.txt python",
    # uv's options ahead of its subcommand.
    "uv -q sync",
    "uv --directory sub sync",
    "uv --offline pip install boto3",
    "uv --color never tool run ruff",
    "uv --offline run --with boto3 python",
    # A module attached to -m.
    "python -mpip install boto3",
    "python3 -Impip install boto3",
    "python -muv sync",
    # Quotes and escapes around options, and inside the values before them.
    'uv run --index-url "https://example.invalid/?a=\\"b" --with boto3 python',
    'uv run --index-url "a\\\\" --with boto3 python',
    "uv run --index-url 'a'\\''b' --with boto3 python",
    "uv run '--with' boto3 python",
    'uv run "--with" boto3 python',
    "uv run --wi'th' boto3 python",
    "uv run '--with=boto3' python",
    "uv run \\--with boto3 python",
    "uv run --index-url https://example.invalid/simple?a=1\\&b=2 --with boto3 python",
    "uv run --index-url a\\;b --with boto3 python",
    "uv run --index-url a\\|b --with boto3 python",
    "'uv' run --with boto3 python",
)


@pytest.mark.parametrize("command", _INSTALL_FORMS)
def test_each_named_install_form_matches(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize("command", _INSTALL_FORMS)
@given(prefix=st.text(max_size=100), suffix=st.text(max_size=100))
def test_install_forms_match_in_surrounding_shell_text(
    command: str, prefix: str, suffix: str
) -> None:
    assert _installs(f"{prefix}\n{command}\n{suffix}")


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
    # A quote holds the --with, so the command it reaches prints it.
    'uv run printf \'%s\' "a \\" --with boto3"; echo ready',
    "uv run printf '%s' 'a --with boto3'; echo ready",
    # An option after the command belongs to the command: uv passes it on.
    "uv run pytest --with boto3",
    "uv run -- echo --with boto3",
    "uv run --extra dev pytest --with boto3",
    # A word spells a uv subcommand only directly after uv, or after uv's options.
    "uv run sync",
    "uv run --offline sync",
    "uv run add.py",
    "uv lock --check",
    "uv export --frozen --no-emit-project",
    "python -I -m uv export --frozen",
    # A comment runs nothing.
    "# pip install boto3",
    "echo ok # uv sync",
    "pip --version # install",
)


@pytest.mark.parametrize("command", _NON_INSTALL_COMMANDS)
def test_non_install_commands_stay_allowed(command: str) -> None:
    assert not _installs(command)


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
    assert not _installs(run)


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
def test_the_install_check_finds_install_commands(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize(
    "command",
    [
        "bash .github/scripts/install-locked.sh --editable",
        "pip --version; echo install",
        "pip list",
    ],
)
def test_the_install_check_ignores_other_commands(command: str) -> None:
    assert not _installs(command)


def _single_quoted(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _double_quoted(text: str) -> str:
    return '"' + re.sub(r'(["\\$`])', r"\\\1", text) + '"'


def _locale_quoted(text: str) -> str:
    return "$" + _double_quoted(text)


def _ansi_quoted(text: str) -> str:
    return "$'" + re.sub(r"(['\\])", r"\\\1", text).replace("\n", "\\n") + "'"


def _backslash_quoted(text: str) -> str:
    return "".join("'\n'" if char == "\n" else "\\" + char for char in text)


_QUOTERS = (
    shlex.quote,
    _single_quoted,
    _double_quoted,
    _locale_quoted,
    _ansi_quoted,
    _backslash_quoted,
)
_WORD_GAPS = st.sampled_from((" ", "\t", "  ", " \\\n\t"))


def _draw_spelling(data: st.DataObject, word: str, *, cut_lines: bool = True) -> str:
    """One word, cut at random points, with each part quoted its own way.

    With cut_lines, a backslash-newline may sit at a cut, which the shell removes.
    """
    cuts = st.sets(st.integers(1, len(word) - 1), max_size=3) if len(word) > 1 else st.just(set())
    edges = sorted(data.draw(cuts))
    spelled = ""
    for start, end in zip([0, *edges], [*edges, len(word)], strict=True):
        if start and cut_lines:
            spelled += data.draw(st.sampled_from(("", "", "\\\n")))
        spelled += data.draw(st.sampled_from(_QUOTERS))(word[start:end])
    return spelled or "''"


def _draw_command(data: st.DataObject, command: str, *, cut_lines: bool = True) -> str:
    """A command with the same words as this one, quoted at random."""
    # shlex can't decode a backslash-newline.
    first, *rest = shlex.split(command.replace("\\\n", ""))
    spelled = _draw_spelling(data, first, cut_lines=cut_lines)
    for word in rest:
        spelled += data.draw(_WORD_GAPS) + _draw_spelling(data, word, cut_lines=cut_lines)
    return spelled


@pytest.mark.parametrize("command", _INSTALL_FORMS)
@given(data=st.data())
def test_install_forms_match_however_their_words_are_quoted(
    command: str, data: st.DataObject
) -> None:
    spelled = _draw_command(data, command)
    assert _installs(spelled), spelled


# These commands' separators and comments lose their meaning once quoted.
_NON_INSTALLS_OF_ONE_COMMAND = tuple(
    command for command in _NON_INSTALL_COMMANDS if not re.search(r"[;&|\n#]", command)
)


@pytest.mark.parametrize("command", _NON_INSTALLS_OF_ONE_COMMAND)
@given(data=st.data())
def test_quoting_does_not_turn_a_command_into_an_install(command: str, data: st.DataObject) -> None:
    spelled = _draw_command(data, command, cut_lines=False)
    assert not _installs(spelled), spelled


def test_a_word_cut_by_a_continuation_also_reads_as_two_words() -> None:
    """The line-by-line reading ends a word at a backslash-newline, so this errs toward flagging."""
    assert _installs("uv sy\\\nnc")
    assert _installs("uvx\\\nfoo")


@pytest.mark.parametrize(
    "command",
    [
        # Quotes that hold a newline.
        "uv run --index-url 'a\nb' --with boto3 python",
        'uv run --index-url "a\nb" --with boto3 python',
        "uv run --index-url $'a\nb' --with boto3 python",
        # ANSI and locale quotes.
        "$'uv' sync",
        "uv run --index-url $'a\\'b' --with boto3 python",
        "uv run $'--with' boto3 python",
        'uv run $"--with" boto3 python',
        "bash -c $'echo ready\\nuv sync'",
        "bash -c $'echo ready\\tuv sync'",
    ],
)
def test_install_forms_match_inside_quotes_that_balance(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize(
    "command",
    [
        "$(uv sync)",
        '"$(uv sync)"',
        "`uv sync`",
        '"`uv sync`"',
        "x=$(uvx ruff)",
        "(uv sync)",
        "{ uv sync; }",
        "if uv sync; then :; fi",
        "while uv sync; do :; done",
        "! uv sync",
        "time uv sync",
        "FOO=1 uv sync",
        "env FOO=1 uv sync",
        "sudo pip install boto3",
        "xargs pip install",
        "cmd=(uv sync)",
        "cat <(uvx ruff)",
        "case x in a) uv sync;; esac",
        "f() { uv sync; }",
        "python -m uv sync",
        ".venv/bin/pip install boto3",
        "/usr/local/bin/uv sync",
        "$HOME/.local/bin/uvx ruff",
        '"$uv" sync',
        '"$(uv sync 2>&1)"',
        "uv run --offline uv sync",
        "uv run python -m pip install boto3",
        # A # opens no comment inside ${...}, or past a backtick's end.
        "echo ${#x}; uv sync",
        "if [ ${#files[@]} -eq 0 ]; then uv sync; fi",
        "echo `# note`; uv sync",
    ],
)
def test_install_forms_match_in_shell_structure(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize(
    "command",
    [
        "bash -c 'uv sync'",
        'bash -lc "pip install boto3"',
        "sh -c 'uv run --with boto3 python'",
        'eval "uvx ruff"',
        'cmd="uv sync"',
        '--command="uv sync"',
        "python -c \"import os; os.system('pip install boto3')\"",
        "python -c \"import subprocess, sys; subprocess.run([sys.executable, '-m', 'pip', "
        "'install', 'boto3'])\"",
        'sudo sh -c "cd x && pip install -e ."',
        "bash -c \"bash -c 'uv sync'\"",
        "trap 'uv sync' EXIT",
        # By design: the check can't tell which programs run their arguments.
        "echo 'uv sync'",
    ],
)
def test_install_forms_match_in_quoted_code(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run 2>&1 --with boto3 python",
        "uv run >log --with boto3 python",
        "uv run > log --with boto3 python",
        "uv run &>log --with boto3 python",
        "uv run >|log --with boto3 python",
        "uv run <in --with boto3 python",
        "uv run 2>/dev/null --with boto3 python",
        ">log uv sync",
        "2>&1 uv sync",
        'uv run >"$(cat name)" --with boto3 python',
        "uv run > $(cat name) --with boto3 python",
        "uv run > $(cat name)suffix --with boto3 python",
    ],
)
def test_redirects_are_not_the_command_uv_runs(command: str) -> None:
    assert _installs(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run $flags --with boto3 python",
        'uv run "${flags[@]}" --with boto3 python',
        "uv run $(cat flags) --with boto3 python",
        "uv run `cat flags` --with boto3 python",
        "uv run --python ${{ matrix.python }} --with boto3 python",
        "uv run ${{ inputs.flags }} --with boto3 python",
        "uv run ${x:-a b c} --with boto3 python",
        "uv $flags sync",
    ],
)
def test_expansions_may_hold_options_so_they_end_nothing(command: str) -> None:
    assert _installs(command)


def test_a_word_after_an_option_may_be_its_value_so_the_options_go_on() -> None:
    """uv run's walk treats --offline's next word as a possible value, by design."""
    assert _installs("uv run --offline pytest --with boto3")
    assert not _installs("uv run --offline=x pytest --with boto3")


@pytest.mark.parametrize("prefix", ["'", '"', "x\\", "$(", "<<EOF", "`", "(", ">", ">\\", "${{"])
def test_a_misread_line_cannot_hide_an_install_on_the_next_line(prefix: str) -> None:
    """A quote the reader misjudges, such as one in a heredoc body, stops at its line's end."""
    for command in _INSTALL_FORMS:
        for closer in ("", "'", '"'):
            text = f"{prefix}\n{command}\n{closer}"
            assert _installs(text), text


def _bash_commands(script: str) -> list[list[str]]:
    """The calls of the shell function f that bash makes when it runs a script."""
    harness = (
        f"exec 3>&1 1>/dev/null\nf() {{ printf '%s\\0' f \"$@\" $'\\1' >&3; }}\n{script}\nwait\n"
    )
    result = subprocess.run(
        ["bash", "-c", harness],
        capture_output=True,
        check=True,
        env={"PATH": os.environ["PATH"]},
        text=True,
    )
    return [record.split("\0")[:-1] for record in result.stdout.split("\x01\0") if record]


_SHELL_PUNCTUATION = " \t\n;&|()<>'\"\\$`#*?[]{}=~!-"
_ARGUMENTS = st.text(alphabet="abc012" + _SHELL_PUNCTUATION, max_size=8)
_REDIRECTS = st.sampled_from(
    (
        "2>&1",
        ">/dev/null",
        ">>/dev/null",
        "&>/dev/null",
        "</dev/null",
        ">|/dev/null",
        "2>/dev/null",
        "<<<x",
    )
)
_COMMAND_SEPARATORS = st.sampled_from(("; ", " && ", "\n", " | ", " & "))
_COMMENTS = st.text(alphabet="abc '\"();&|$`\\", max_size=8)


def _draw_call(data: st.DataObject, depth: int) -> str:
    """A call of f whose words hold quotes, redirects and command substitutions."""
    call = "f"
    for _ in range(data.draw(st.integers(0, 3))):
        kind = data.draw(st.sampled_from(("word", "word", "redirect", "$()", '"$()"', "``")))
        if kind == "redirect":
            call += " " + data.draw(_REDIRECTS)
        elif kind == "``":
            call += " `f " + data.draw(st.text(alphabet="abc012", min_size=1, max_size=3)) + "`"
        elif kind == "word" or depth == 0:
            call += " " + _draw_spelling(data, data.draw(_ARGUMENTS))
        elif kind == "$()":
            call += f" $({_draw_call(data, depth - 1)})"
        else:
            call += f' "$({_draw_call(data, depth - 1)})"'
    return call


def _draw_script(data: st.DataObject) -> str:
    calls = []
    for _ in range(data.draw(st.integers(1, 4))):
        call = _draw_call(data, depth=2)
        calls.append(f"({call})" if data.draw(st.booleans()) else call)
    script = calls[0]
    for call in calls[1:]:
        # A comment's newline already ends the command before it.
        comment = data.draw(st.one_of(st.none(), _COMMENTS))
        separator = data.draw(_COMMAND_SEPARATORS) if comment is None else f" # {comment}\n"
        script += separator + call
    return script


@given(data=st.data())
@settings(deadline=None)
def test_the_reader_finds_the_commands_bash_runs(data: st.DataObject) -> None:
    script = _draw_script(data)
    assert sorted(_read_shell(script).commands) == sorted(_bash_commands(script)), script


@given(words=st.lists(st.text(max_size=20), min_size=1, max_size=6))
def test_the_reader_undoes_shlex_join(words: list[str]) -> None:
    assert _read_shell(shlex.join(words)).commands == [words]


def _nest_double_quotes(text: str, size: int) -> str:
    """Text inside as many layers of double quotes as fit, each escaping the last.

    The layers escape only quotes and backslashes, so text's $ stays one byte in every
    layer and each reading of a layer takes the slow path through all of it.
    """
    while True:
        nested = '"' + re.sub(r'(["\\])', r"\\\1", text) + '"'
        if len(nested) > size:
            return text
        text = nested


_SCAN_LIMIT_SECONDS = 2.0
_HARD_TO_SCAN = {
    "the review's repeated uv run": 'uv run "x" ' * 10_000,
    "uv and an option": "uv --x " * 16_000,
    "uv run and an option": "uv run --x uv --x run --x " * 4_200,
    "single quotes": "' " * 55_000,
    "double quotes": '" ' * 55_000,
    "one open double quote": '"' + "a " * 55_000,
    "backslashes": "\\" * 110_000,
    "escaped double quotes": '\\"' * 55_000,
    "open substitutions": "$(" * 55_000,
    "backticks": "`" * 110_000,
    "open subshells": "(" * 110_000,
    "heredoc markers": "<<x\n" * 27_500,
    "open expressions": "${{ " * 27_500,
    "repeated quoted words": '"a b" ' * 18_000,
    "distinct quoted words": "".join(f'"{index} b" ' for index in range(12_000)),
    "layers of double quotes": _nest_double_quotes("$ " * 50_000, 110_000),
    "layers of shlex quotes": shlex.quote(shlex.quote(shlex.quote("uv run --x " * 10_000))),
    "an open quote over many lines": "'" + "uv run\n" * 15_000 + "'",
    "pip without install": "pip " * 27_500,
    "plain letters": "a" * 110_000,
    "many short words": "a " * 55_000,
    "one long option": "-" + "a" * 110_000,
}


@pytest.mark.parametrize("text", _HARD_TO_SCAN.values(), ids=_HARD_TO_SCAN.keys())
def test_the_install_scan_stays_within_its_time_bound(text: str) -> None:
    """Each input holds over 100 KB and no install, so the scan reads all of it."""
    assert len(text) > 100_000
    started = time.process_time()
    assert not _installs(text)
    assert time.process_time() - started < _SCAN_LIMIT_SECONDS


@pytest.mark.parametrize(
    "shell",
    [
        "bash --rcfile /some/path/python.rc {0}",
        "bash --rcfile python {0}",
        "bash --noprofile --norecurse -eo pipefail {0}",
        "sh -e {0}",
        "pwsh -command \". '{0}'\"",
        "/usr/bin/env bash --rcfile /some/path/python.rc {0}",
    ],
)
def test_a_shell_argument_does_not_make_a_step_project_code(tmp_path: Path, shell: str) -> None:
    workflow = tmp_path / "shell.yml"
    workflow.write_text(
        yaml.safe_dump(
            {"jobs": {"example": {"steps": [{"name": "shell", "shell": shell, "run": "ls"}]}}}
        ),
        encoding="utf-8",
    )
    test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow)


@pytest.mark.parametrize(
    "shell",
    [
        "/usr/bin/python3 {0}",
        "python3.14 {0}",
        "/usr/bin/env python3 {0}",
        "bash -c 'python3 {0}'",
        "pytest {0}",
    ],
)
def test_a_program_in_a_step_shell_makes_it_project_code(tmp_path: Path, shell: str) -> None:
    workflow = tmp_path / "shell.yml"
    workflow.write_text(
        yaml.safe_dump(
            {"jobs": {"example": {"steps": [{"name": "early", "shell": shell, "run": "ls"}]}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="example: early"):
        test_every_job_that_runs_project_code_installs_it_from_the_lock(workflow)


def test_a_step_shell_can_install_outside_the_script(tmp_path: Path) -> None:
    workflow = tmp_path / "shell.yml"
    step = {"name": "ephemeral", "shell": "uv run --with boto3 python {0}", "run": "import boto3"}
    workflow.write_text(yaml.safe_dump({"jobs": {"example": {"steps": [step]}}}), encoding="utf-8")
    assert _installs_outside_the_script(workflow) == ["example: ephemeral"]


def test_install_script_installs_dependencies_only_with_hashes_from_wheels() -> None:
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    commands = re.sub(r"\\\n\s*", " ", script)
    installs = [
        line.strip()
        for line in commands.splitlines()
        if _installs(line) and not line.lstrip().startswith("#")
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
