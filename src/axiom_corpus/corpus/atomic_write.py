"""Write a file so that its final path only ever holds a complete copy."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Suffix of the temporary file a write goes through. The root .gitignore ignores
# hidden files with this suffix under .axiom/, so one left by a killed process
# never reaches a commit.
ATOMIC_WRITE_TEMP_SUFFIX = ".tmp"


def write_bytes_atomically(target: Path, data: bytes) -> None:
    """Write ``data`` to ``target`` through a temporary file in the same directory.

    The bytes are written and fsynced to the temporary file, which is then
    renamed over ``target`` (mode 0644). Until the rename, ``target`` keeps
    whatever it held before (or stays absent). An exception at any step,
    KeyboardInterrupt included, removes the temporary file. A process killed
    outright (SIGTERM, SIGKILL) can leave it behind as
    ``.<name>.<random>.tmp``. The lock reader skips hidden files and the
    manifest reader reads only ``*.json``, so neither takes it for a lock or a
    manifest.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=ATOMIC_WRITE_TEMP_SUFFIX
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
