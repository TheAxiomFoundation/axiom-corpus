#!/usr/bin/env python
"""Emit or verify a signed corpus release manifest.

Examples:
    # Emit the r0 manifest for the current corpus state.
    uv run python scripts/release_manifest.py emit-release-manifest \
        --base data/corpus --out releases/r0/release_manifest.json

    # Verify it (rehash artifacts + check the HMAC signature if the key is set).
    AXIOM_CORPUS_RELEASE_SIGNING_KEY=... \
        uv run python scripts/release_manifest.py verify-release-manifest \
        --manifest releases/r0/release_manifest.json

Thin wrapper around ``axiom_corpus.release.cli`` for callers that prefer a
script entrypoint matching existing repo style. Equivalent to the
``axiom-corpus-release`` console script.
"""

from __future__ import annotations

import sys

from axiom_corpus.release.cli import main as release_main


def main(argv: list[str] | None = None) -> int:
    return release_main(argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
