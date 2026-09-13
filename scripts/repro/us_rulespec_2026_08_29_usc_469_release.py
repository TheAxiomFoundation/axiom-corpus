#!/usr/bin/env python3
"""Build the US RuleSpec successor release carrying 26 USC 469."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_RELEASE = "us-rulespec-2026-08-23-canada-338-suspension-union"
RELEASE = "us-rulespec-2026-08-29-usc-469-union"
REPLACED_SCOPE = {
    "document_class": "statute",
    "jurisdiction": "us",
    "version": "2026-08-03-rulespec-title-26-current-union",
}
REPLACEMENT_SCOPE = {
    "document_class": "statute",
    "jurisdiction": "us",
    "version": "2026-08-29-rulespec-title-26-with-469-union",
}


def build_release(*, release_dir: Path, output_dir: Path | None = None) -> Path:
    """Replace Title 26 with its reviewed section 469 successor."""
    source = release_dir / f"{BASE_RELEASE}.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    scopes = payload["scopes"]
    if scopes.count(REPLACED_SCOPE) != 1:
        raise ValueError("base release must contain the prior Title 26 union once")
    if REPLACEMENT_SCOPE in scopes:
        raise ValueError("section 469 Title 26 successor already exists in base release")

    final_scopes = sorted(
        [REPLACEMENT_SCOPE if scope == REPLACED_SCOPE else scope for scope in scopes],
        key=lambda scope: (
            scope["jurisdiction"],
            scope["document_class"],
            scope["version"],
        ),
    )
    identities = {
        (scope["jurisdiction"], scope["document_class"], scope["version"])
        for scope in final_scopes
    }
    if len(identities) != len(final_scopes):
        raise ValueError("release selector would contain duplicate scopes")

    payload.update(
        {
            "description": (
                f"Successor to {BASE_RELEASE}. It preserves every other prior scope and "
                "replaces the prior consolidated Title 26 scope with its "
                "collision-free successor carrying the source-complete 26 USC "
                "469 hierarchy needed for the first shared QBI/NIIT "
                "business-activity slice."
            ),
            "name": RELEASE,
            "scopes": final_scopes,
        }
    )
    output = (output_dir or release_dir) / f"{RELEASE}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, default=Path("manifests/releases"))
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(build_release(release_dir=args.release_dir, output_dir=args.output_dir))


if __name__ == "__main__":
    main()
