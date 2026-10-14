"""``write_bytes_atomically``: the target holds the old bytes or all the new ones.

Invariant, for any prior state and any step of the write that fails (an
exception or Ctrl-C): the target is exactly what it was before (absent, or the
prior bytes), and the directory holds nothing else, so no temporary file is
left. A write that does not fail leaves exactly the new bytes, mode 0644.
"""

from __future__ import annotations

import errno
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from axiom_corpus.corpus import atomic_write
from axiom_corpus.corpus.atomic_write import write_bytes_atomically

REPO_ROOT = Path(__file__).resolve().parents[1]

# The ``os`` functions the write goes through; failing ``fdopen`` means the
# write itself fails after half the bytes reach the temporary file.
FAILING_STEPS = ("fdopen", "fsync", "chmod", "replace")


class _WritesHalfThenRaises:
    """A file handle whose ``write`` writes half the bytes, flushes, then raises."""

    def __init__(self, handle: Any, exc: BaseException) -> None:
        self._handle = handle
        self._exc = exc

    def __enter__(self) -> _WritesHalfThenRaises:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._handle.close()

    def write(self, data: bytes) -> int:
        self._handle.write(data[: len(data) // 2])
        self._handle.flush()
        raise self._exc

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)


class _FaultyOs:
    """``os`` as ``atomic_write`` sees it, with one step raising ``exc``."""

    def __init__(self, step: str, exc: BaseException) -> None:
        self._step = step
        self._exc = exc

    def __getattr__(self, name: str) -> Any:
        real = getattr(os, name)
        if name != self._step:
            return real
        if name == "fdopen":
            return lambda fd, *args, **kwargs: _WritesHalfThenRaises(
                real(fd, *args, **kwargs), self._exc
            )

        def fail(*_args: object, **_kwargs: object) -> None:
            raise self._exc

        return fail


def _interruptions() -> st.SearchStrategy[BaseException]:
    return st.sampled_from(
        [
            OSError(errno.ENOSPC, "No space left on device"),
            OSError(errno.EIO, "Input/output error"),
            KeyboardInterrupt(),
        ]
    )


@settings(max_examples=200, deadline=None)
@given(
    prior=st.none() | st.binary(max_size=4096),
    data=st.binary(max_size=4096),
    step=st.none() | st.sampled_from(FAILING_STEPS),
    exc=_interruptions(),
)
def test_target_is_prior_or_complete_and_no_temp_file_is_left(
    prior: bytes | None, data: bytes, step: str | None, exc: BaseException
) -> None:
    with tempfile.TemporaryDirectory() as raw, pytest.MonkeyPatch.context() as patch:
        directory = Path(raw) / "scope"
        target = directory / "2026-10-14.json"
        if prior is not None:
            directory.mkdir()
            target.write_bytes(prior)
        if step is not None:
            patch.setattr(atomic_write, "os", _FaultyOs(step, exc))
            with pytest.raises(type(exc)):
                write_bytes_atomically(target, data)
            if prior is None:
                assert not target.exists()
                assert not directory.exists() or os.listdir(directory) == []
            else:
                assert target.read_bytes() == prior
                assert os.listdir(directory) == [target.name]
            return
        write_bytes_atomically(target, data)
        assert target.read_bytes() == data
        assert os.listdir(directory) == [target.name]
        assert target.stat().st_mode & 0o777 == 0o644


def test_creates_missing_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / ".axiom/ingest-manifests/nz/statute/2026-10-14.json"

    write_bytes_atomically(target, b"{}\n")

    assert target.read_bytes() == b"{}\n"


def test_replaces_a_symlink_rather_than_writing_through_it(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside\n")
    target = tmp_path / "scope" / "2026-10-14.json"
    target.parent.mkdir()
    target.symlink_to(outside)

    write_bytes_atomically(target, b"new\n")

    assert not target.is_symlink()
    assert target.read_bytes() == b"new\n"
    assert outside.read_bytes() == b"outside\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout


@pytest.mark.parametrize(
    "relative",
    [
        ".axiom/ingest-manifests/nz/statute/2026-10-14.json",
        ".axiom/corpus-locks/nz/statute/2026-10-14.json",
    ],
)
def test_temp_file_of_a_killed_write_is_git_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    """While a write is in flight its temporary file is invisible to ``git add``.

    A process killed outright never reaches the ``finally`` that removes the
    temporary file, so the repository's .gitignore must keep it out of
    ``git add .axiom/ingest-manifests`` (scripts/sign_release_scopes.sh) and out
    of the guard's untracked-lock listing.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    shutil.copyfile(REPO_ROOT / ".gitignore", repo / ".gitignore")
    target = repo / relative
    seen: dict[str, str] = {}

    def replace_after_looking(src: str | Path, dst: str | Path) -> None:
        seen["temp"] = Path(src).relative_to(repo).as_posix()
        seen["status"] = _git(repo, "status", "--porcelain", "--untracked-files=all")
        seen["ignored"] = _git(repo, "check-ignore", seen["temp"]).strip()
        os.replace(src, dst)

    class _LookingOs:
        def __getattr__(self, name: str) -> Any:
            return replace_after_looking if name == "replace" else getattr(os, name)

    monkeypatch.setattr(atomic_write, "os", _LookingOs())
    write_bytes_atomically(target, b"{}\n")

    temp_name = Path(seen["temp"]).name
    assert temp_name.startswith(f".{target.name}.")
    assert temp_name.endswith(atomic_write.ATOMIC_WRITE_TEMP_SUFFIX)
    assert seen["ignored"] == seen["temp"]
    assert seen["status"] == "?? .gitignore\n"
    # The rule must not hide the lock or manifest itself.
    assert sorted(_git(repo, "status", "--porcelain", "--untracked-files=all").splitlines()) == [
        f"?? {relative}",
        "?? .gitignore",
    ]
