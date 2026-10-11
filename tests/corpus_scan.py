"""pytest-timeout budget for tests that parse the whole provision corpus.

CI runs the suite with a flat ``--timeout=60``. A few tests json-parse every row
under data/corpus/provisions, so their cost tracks corpus size, not their own
code, and the corpus keeps growing. Before the citation-path grammar scan
streamed rows, a slow runner pushed it past that flat 60 s (axiom-corpus#736).

``corpus_scan`` budgets such a test by corpus size instead: 1 s per 10 MB of
provision JSONL, never below the suite's 60 s and never above 20 minutes. The
10 MB/s floor sits far below the rates CI scans at, so the budget tracks growth
while a genuine hang still fails with pytest-timeout's traceback.
"""

from __future__ import annotations

import glob
import math
import os
from pathlib import Path

import pytest

PROVISIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "corpus" / "provisions"
# Keep in sync with --timeout in .github/workflows/ci.yml: a marker replaces that
# value, so a lower number here would shorten these tests' limit on a small tree.
SUITE_TIMEOUT_SECONDS = 60
MIN_SCAN_BYTES_PER_SECOND = 10_000_000
# The test job has timeout-minutes: 30. Stay inside it so a hang is reported by
# pytest-timeout, not cut off by the runner.
MAX_TIMEOUT_SECONDS = 20 * 60


def provision_jsonl_bytes(provisions_dir: Path = PROVISIONS_DIR) -> int:
    """Total size of the provision JSONL under ``provisions_dir``."""
    total = 0
    # Same listing as scripts/validate_citation_paths.py's loader.
    for filename in glob.glob(str(provisions_dir / "**" / "*.jsonl"), recursive=True):
        try:
            total += os.path.getsize(filename)
        except OSError:
            # E.g. a dangling link: leave it to the scan itself to fail on, rather
            # than aborting collection of the whole session here.
            continue
    return total


def corpus_scan_timeout(corpus_bytes: int) -> int:
    """Seconds allowed for one full parse of ``corpus_bytes`` of provision JSONL."""
    scaled = math.ceil(corpus_bytes / MIN_SCAN_BYTES_PER_SECOND)
    return min(MAX_TIMEOUT_SECONDS, max(SUITE_TIMEOUT_SECONDS, scaled))


corpus_scan = pytest.mark.timeout(corpus_scan_timeout(provision_jsonl_bytes()))
