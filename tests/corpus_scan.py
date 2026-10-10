"""pytest-timeout budget for tests that parse the whole provision corpus.

CI runs the suite with a flat ``--timeout=60``. Three tests json-parse every row
under data/corpus/provisions: the ``result`` fixture in
test_citation_path_grammar.py, the identity-convention check in
test_provision_identity_convention.py, and the evidence-span check in
test_claims.py. Their cost tracks corpus size, not their own code, and the corpus
keeps growing: 0.95 GB at the end of 2026-08-01, 2.28 GB on 2026-09-22, 2.69 GB
on 2026-10-10. Before the grammar scan streamed rows it took 44-48 s of the 60 s
on passing CI runs and timed out on slower runners (axiom-corpus#736). Since
then the three scans have taken 8-23 s on CI.

``corpus_scan`` budgets such a test by corpus size instead: 1 s per 10 MB of
provision JSONL, never below the suite's 60 s. The slowest CI scan measured since
streaming ran at 118 MB/s, so the floor sits an order of magnitude below it while
a genuine hang still fails within minutes.
"""

from __future__ import annotations

import glob
import math
import os
from pathlib import Path

import pytest

PROVISIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "corpus" / "provisions"
SUITE_TIMEOUT_SECONDS = 60
MIN_SCAN_BYTES_PER_SECOND = 10_000_000


def corpus_scan_timeout(provisions_dir: Path = PROVISIONS_DIR) -> int:
    """Seconds allowed for one full parse of the provision JSONL under ``provisions_dir``."""
    corpus_bytes = 0
    # Same listing as scripts/validate_citation_paths.py's loader.
    for filename in glob.glob(str(provisions_dir / "**" / "*.jsonl"), recursive=True):
        try:
            corpus_bytes += os.path.getsize(filename)
        except OSError:
            # E.g. a dangling link: leave it to the scan itself to fail on, rather
            # than aborting collection of the whole session here.
            continue
    return max(SUITE_TIMEOUT_SECONDS, math.ceil(corpus_bytes / MIN_SCAN_BYTES_PER_SECOND))


corpus_scan = pytest.mark.timeout(corpus_scan_timeout())
